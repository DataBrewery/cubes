# -*- coding=utf -*-
from ...browser import *
from ...errors import *
from ...model import *
from ...common import get_logger

from .store import DEFAULT_TIME_HIERARCHY

import datetime
import calendar
from collections import OrderedDict, defaultdict

_measure_param = {
        "total": "general",
        "unique": "unique",
        "average": "average"
    }

def _week_value(dt, as_string=False):
    """
    Mixpanel weeks start on Monday. Given a datetime object or a date string of format YYYY-MM-DD,
    returns a YYYY-MM-DD string for the Monday of that week.
    """
    dt = datetime.datetime.strptime(dt, '%Y-%m-%d') if isinstance(dt, basestring) else dt
    dt = ( dt - datetime.timedelta(days=dt.weekday()) )
    return ( dt.strftime("%Y-%m-%d") if as_string else dt )

_week_path_readers = ( lambda v: datetime.datetime.strptime(v, '%Y-%m-%d'), lambda v: datetime.datetime.strptime(v, '%Y-%m-%d'), int )

_lower_date = datetime.datetime(2000, 1, 1)

def coalesce_date_path(path, bound, hier='ymdh'):
    if hier == 'wdh':
        return _coalesce_date_wdh(path, bound)
    else:
        return _coalesce_date_ymdh(path, bound)

def _coalesce_date_wdh(path, bound):
    path = [ _week_path_readers[i](path[i]) for i, v in enumerate(list(path or [])) ]
    effective_dt = path[1] if len(path) > 1 else ( path[0] if len(path) else ( _lower_date if bound == 0 else datetime.datetime.today() ) )

    if bound == 0:
        # at week level, first monday
        if len(path) < 1:
            return _week_value(effective_dt)
        else:
            return effective_dt.replace(hour=0)
    else:
        # end of this week, sunday
        result = ( _week_value(effective_dt) + datetime.timedelta(days=6) ) if len(path) < 2 else effective_dt
        return min(result, datetime.datetime.today())


def _coalesce_date_ymdh(path, bound):
    # Bound: 0: lower, 1:upper

    # Convert path elements
    path = [ int(v) for v in list(path or []) ]

    length = len(path)

    # Lower bound:
    if bound == 0:
        lower = [_lower_date.year, _lower_date.month, _lower_date.day]
        result = path + lower[len(path):]
        return datetime.datetime(**(dict(zip(['year', 'month', 'day'], result))))

    # Upper bound requires special handling
    today = datetime.datetime.today()

    delta = datetime.timedelta(1)
    # Make path of length 3
    (year, month, day) = tuple(path + [None]*(3-len(path)))

    if not year:
        return today

    elif year and month and day:
        date = datetime.date(year, month, day)

    elif year < today.year:
        date = datetime.date(year+1, 1, 1) - delta

    elif year == today.year and month and month < today.month:
        day = calendar.monthrange(year, month)[1]
        date = datetime.date(year, month, day)

    elif year == today.year and month == today.month and not day:
        date = datetime.date(year, month, today.day)

    elif year > today.year:
        month = month or 1
        day = calendar.monthrange(year, month)[1]
        date = datetime.date(year, month, day)

    else:
        date = today

    return date

def time_to_path(time_string, last_level, hier='ymdh'):
    """Converts `time_string` into a time path. `time_string` can have format:
        ``yyyy-mm-dd`` or ``yyyy-mm-dd hh:mm:ss``. Only hour is considered
        from the time."""

    split = time_string.split(" ")
    if len(split) > 1:
        date, time = split
    else:
        date = split[0]
        time = None

    if hier == 'wdh':
        if last_level == 'week':
            time_path = [ _week_value(date, True) ]
        else:
            time_path = [ _week_value(date, True), date ]
    else:
        time_path = [int(v) for v in date.split("-")]
    # Only hour is assumed
    if time:
        hour = time.split(":")[0]
        time_path.append(int(hour))

    return tuple(time_path)


class MixpanelBrowser(AggregationBrowser):
    def __init__(self, cube, store, locale=None, metadata=None, **options):
        """Creates a Mixpanel aggregation browser.

        Requirements and limitations:

        * `time` dimension should always be present in the drilldown
        * only one other dimension is allowd for drilldown
        * range cuts assume numeric dimensions
        * unable to drill-down on `year` level, will default to `month`
        """
        self.store = store
        self.cube = cube
        self.options = options
        self.logger = get_logger()

    def aggregate(self, cell=None, measures=None, drilldown=None, split=None,
                    **options):

        if split:
            raise BrowserError("split in mixpanel is not supported")

        # TODO: this is incosistent with "if nothing explicit, then all"
        measures = measures or ["total"]
        measures = self.cube.get_measures(measures)
        measure_names = [m.name for m in measures]

        # Get the cell and prepare cut parameters
        cell = cell or Cell(self.cube)

        #
        # Prepare drilldown
        #
        drilldown = Drilldown(drilldown, cell)

        if "time" in drilldown and len(drilldown) > 2:
            raise ArgumentError("Can not drill down with more than one "
                                "non-time dimension in mixpanel")

        #
        # Create from-to date range from time dimension cut
        #
        time_cut = cell.cut_for_dimension("time")
        if not time_cut:
            path_time_from = []
            path_time_to = []
        elif isinstance(time_cut, PointCut):
            path_time_from = time_cut.path or []
            path_time_to = time_cut.path or []
        elif isinstance(time_cut, RangeCut):
            path_time_from = time_cut.from_path or []
            path_time_to = time_cut.to_path or []
        else:
            raise ArgumentError("Mixpanel does not know how to handle cuts "
                                "of type %s" % type(time_cut))

        path_time_from = coalesce_date_path(path_time_from, 0, time_cut.hierarchy)
        path_time_to = coalesce_date_path(path_time_to, 1, time_cut.hierarchy)

        params = {
                "event": self.cube.name,
                "from_date": path_time_from.strftime("%Y-%m-%d"),
                "to_date": path_time_to.strftime("%Y-%m-%d")
            }

        time_level = drilldown.last_level("time")
        if time_level:
            time_level = str(time_level)
            time_hier = str(drilldown['time'].hierarchy)
        else:
            time_hier = DEFAULT_TIME_HIERARCHY

        # time_level - as requested by the caller
        # actual_time_level - time level in the result (dim.hierarchy
        #                     labeling)
        # mixpanel_unit - mixpanel request parameter

        if not time_level or time_level == "year":
            mixpanel_unit = actual_time_level = "month"
            # Get the default hierarchy
        elif time_level == "date":
            mixpanel_unit = "day"
            actual_time_level = "date"
        else:
            mixpanel_unit = actual_time_level = str(time_level)

        if time_level != actual_time_level:
            self.logger.debug("Time drilldown coalesced from %s to %s" % \
                                    (time_level, actual_time_level))

        if time_level not in self.cube.dimension("time").level_names:
            raise ArgumentError("Can not drill down time to '%s'" % time_level)

        params["unit"] = mixpanel_unit

        # Get drill-down dimension (mixpanel "by" segmentation menu)
        # Assumption: first non-time

        drilldown_on = None
        for obj in drilldown:
            if obj.dimension.name != "time":
                drilldown_on = obj

        if drilldown_on:
            params["on"] = 'properties["%s"]' % \
                                    self._property(drilldown_on.dimension)

        cuts = [cut for cut in cell.cuts if str(cut.dimension) != "time"]

        #
        # The Conditions
        # ==============
        #
        # Create 'where' condition from cuts
        # Assumption: all dimensions are flat dimensions

        conditions = []
        for cut in cuts:
            if isinstance(cut, PointCut):
                condition = self._point_condition(cut.dimension, cut.path[0], cut.invert)
                conditions.append(condition)
            elif isinstance(cut, RangeCut):
                condition = self._range_condition(cut.dimension,
                                                  cut.from_path[0],
                                                  cut.to_path[0], cut.invert)
                conditions.append(condition)
            elif isinstance(cut, SetCut):
                set_conditions = []
                for path in cut.paths:
                    condition = self._point_condition(cut.dimension, path[0])
                    set_conditions.append(condition)
                condition = " or ".join(set_conditions)
                conditions.append(condition)

        if len(conditions) > 1:
            conditions = [ "(%s)" % cond for cond in conditions ]
        if conditions:
            condition = " and ".join(conditions)
            params["where"] = condition

        if "limit" in options:
            params["limit"] = options["limit"]

        #
        # The request
        # ===========
        # Perform one request per measure.
        #

        responses = {}
        for measure in measure_names:
            params["type"] = _measure_param[measure]
            response = self.store.request(["segmentation"],
                                            params)
            self.logger.debug(response['data'])
            responses[measure] = response


        # TODO: get this: result.total_cell_count = None
        # TODO: compute summary

        #
        # The Result
        # ==========
        #

        result = AggregationResult(cell, measures)
        result.cell = cell

        aggregator = _MixpanelResponseAggregator(self, responses,
                        measure_names, drilldown, actual_time_level)

        result.cells = aggregator.cells

        result.levels = drilldown.levels_dictionary()

        return result

    def _property(self, dim):
        """Return correct property name from dimension."""
        dim = str(dim)
        return self.cube.mappings.get(dim, dim)

    def _point_condition(self, dim, value, invert):
        """Returns a point cut for flat dimension `dim`"""

        op = '!=' if invert else '=='
        condition = '(string(properties["%s"]) %s "%s")' % \
                        (self._property(dim), op, str(value))
        return condition

    def _range_condition(self, dim, from_value, to_value, invert):
        """Returns a point cut for flat dimension `dim`. Assumes number."""

        condition_tmpl = (
            '(number(properties["%s"]) >= %s and number(properties["%s"]) <= %s)' if not invert else
            '(number(properties["%s"]) < %s or number(properties["%s"]) > %s)' 
            )

        condition = condition_tmpl % (self._property(dim), from_value, self._property(dim), to_value)
        return condition

# Separated aggregation for better maintainability
class _MixpanelResponseAggregator(object):
    def __init__(self, browser, responses, measure_names, drilldown,
                    actual_time_level):
        """Aggregator for multiple mixpanel responses (multiple dimensions)
        with drill-down post-aggregation.

        Arguments:

        * `browser` – owning browser
        * `reposnes` – mixpanel responses by `measure_names`
        * `measure_names` – list of collected measures
        * `drilldown` – a `Drilldown` object from the browser aggregation
          query

        Object attributes:

        * `measure_names` – list of measure names from the response
        * `measure_data` – a dictionary where keys are measure names and
          values are actual data points.

        * `time_cells` – an ordered dictionary of collected cells from the
          response. Key is time path, value is cell contents without the time
          dimension.
        """
        self.browser = browser
        self.logger = browser.logger
        self.drilldown = drilldown
        self.measure_names = measure_names
        self.actual_time_level = actual_time_level

        # Extract the data
        self.measure_data = {}
        for measure in measure_names:
            self.measure_data = responses[measure]["data"]["values"]

        # Get time drilldown levels, if we are drilling through time
        try:
            time_drilldown = drilldown["time"]
        except KeyError:
            time_drilldown = None
            self.last_time_level = None
            self.time_levels = []
            self.time_herarchy = DEFAULT_TIME_HIERARCHY
        else:
            self.last_time_level = str(time_drilldown.levels[-1])
            self.time_levels = ["time."+str(l) for l in time_drilldown.levels]
            self.time_hierarchy = str(time_drilldown.hierarchy)

        self.logger.debug("Time: hier:%s last:%s all:%s" % \
                            (self.time_hierarchy, self.last_time_level,
                            self.time_levels) )

        self.drilldown_on = None
        for obj in drilldown:
            if obj.dimension.name != "time":
                self.drilldown_on = obj

        # Time-keyed cells:
        #    (time_path, group) -> dictionary

        self.time_cells = {}
        self.cells = []

        # Do it:
        #
        # Collect, Map&Reduce, Order
        # ==========================
        #
        # Process the response. The methods are operating on the instance
        # variable `time_cells`

        self._collect_cells()
        # TODO: handle week
        if actual_time_level != self.last_time_level:
            self._reduce_cells()
        self._finalize_cells()

        # Result is stored in the `cells` instance variable.

    def _collect_cells(self):

        for measure in self.measure_names:
            self._collect_measure_cells(measure)

    def _collect_measure_cells(self, measure):
        """Collects the cells from the response in a time series dictionary
        `time_cells` where keys are tuples: `(time_path, group)`. `group` is
        drill-down key value for the cell, such as `New York` for `city`."""

        # Note: For no-drilldown this would be only one pass and group will be
        # a cube name

        # TODO: To add multiple drill-down dimensions in the future, add them
        # to the `group` part of the key tuple

        for group_key, group_series in self.measure_data.items():

            for time_key, value in group_series.items():
                time_path = time_to_path(time_key, self.last_time_level,
                                                        self.time_hierarchy)
                key = (time_path, group_key)

                self.logger.debug("adding cell %s" % (key, ))
                cell = self.time_cells.setdefault(key, {})
                cell[measure] = value

                # FIXME: do this only on drilldown
                if self.drilldown_on:
                    cell[self.drilldown_on] = group_key

    def _reduce_cells(self):
        """Reduce the cells according to the time dimensions."""

        def reduce_cell(result, cell):
            # We assume only _sum aggergation
            # All measures should be prepared so we can to this
            for measure in self.measure_names:
                result[measure] = result.get(measure, 0) + cell.get(measure, 0)
            return result

        # 1. Map cells to reduced time path
        #
        reduced_map = defaultdict(list)
        reduced_len = len(self.time_levels)

        for key, cell in self.time_cells.items():
            time_path = key[0]
            reduced_path = time_path[0:reduced_len]

            reduced_key = (reduced_path, key[1])

            self.logger.debug("reducing %s -> %s" % (key, reduced_key))
            reduced_map[reduced_key].append(cell)

        self.browser.logger.debug("response cell count: %s reduced to: %s" %
                                    (len(self.time_cells), len(reduced_map)))

        # 2. Reduce the cells
        # 
        # See the function reduce_cell() above for aggregation:
        # 
        reduced_cells = {}
        for key, cells in reduced_map.items():
            # self.browser.logger.debug("Reducing: %s -> %s" % (key, cells))
            cell = reduce(reduce_cell, cells, {})

            reduced_cells[key] = cell

        self.time_cells = reduced_cells

    def _finalize_cells(self):
        """Orders the `time_cells` according to the time and "the other"
        dimension and puts the result into the `cells` instance variable.
        This method also adds the time dimension keys."""
        # Order by time (as path) and then drilldown dimension value (group)
        # The key[0] is a list of paths: time, another_drilldown

        order = lambda left, right: cmp(left[0], right[0])
        cells = self.time_cells.items()
        cells.sort(order)

        self.cells = []
        for key, cell in cells:
            # If we are aggregating at finer granularity than "all":
            time_key = key[0]
            if time_key:
                cell.update(zip(self.time_levels, time_key))

            self.cells.append(cell)

