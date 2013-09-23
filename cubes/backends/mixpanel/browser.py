# -*- coding=utf -*-
from ...browser import *
from ...errors import *
from ...model import *
from cubes.common import get_logger

import datetime
import calendar
from collections import OrderedDict

_measure_param = {
        "total": "general",
        "unique": "unique",
        "average": "average"
    }

_no_cut_time_= {
    'from': [2000, 1, 1],
    'to': [2199, 12, 31]
}

def coalesce_date_path(path, bound):
    # Bound: 0: lower, 1:upper
    # Convert items to integers
    path = [int(v) for v in list(path or [])]

    length = len(path)

    # Lower bound:
    if bound == 0:
        lower = [2000, 1, 1]
        result = tuple(path + lower[len(path):])
        return result

    # Upper bound:
    today = datetime.datetime.today()
    upper = [today.year, today.month, today.day]
    delta = datetime.timedelta(1)
    # Make path of length 3
    (year, month, day) = tuple(path + [None]*(3-len(path)))

    if not year:
        return tuple(upper)
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

    return (date.year, date.month, date.day)

def time_to_path(time_string):
    """Converts `time_string` into a time path. `time_string` can have format:
        ``yyyy-mm-dd`` or ``yyyy-mm-dd hh:mm:ss``. Only hour is considered
        from the time."""

    split = time_string.split(" ")
    if len(split) > 1:
        date, time = split
    else:
        date = split[0]
        time = None

    time_path = [int(v) for v in date.split("-")]
    # Only hour is assumed
    if time:
        hour = time.split(":")[0]
        time_path.append(int(hour))

    return time_path


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

        if not "time" in drilldown:
            raise ArgumentError("Time dimension drilldown is required for mixpanel")
        elif len(drilldown) > 2:
            raise ArgumentError("Can not drill down with more than one "
                                "non-time dimension in mixpanel")

        #
        # Create from-to date range from time dimension cut
        #
        time_cut = cell.cut_for_dimension("time")
        if not time_cut:
            path_time_from = _no_cut_time_paths['from']
            path_time_to = _no_cut_time_paths['to']
        elif isinstance(time_cut, PointCut):
            path_time_from = time_cut.path or []
            path_time_to = time_cut.path or []
        elif isinstance(time_cut, RangeCut):
            path_time_from = time_cut.from_path or []
            path_time_to = time_cut.to_path or []
        else:
            raise ArgumentError("Mixpanel does not know how to handle cuts "
                                "of type %s" % type(time_cut))

        path_time_from = coalesce_date_path(path_time_from, 0)
        path_time_to = coalesce_date_path(path_time_to, 1)

        params = {
                "event": self.cube.name,
                "from_date": ("%s-%s-%s" % path_time_from),
                "to_date": ("%s-%s-%s" % path_time_to)
            }

        time_level = str(drilldown.last_level("time"))

        if time_level == "year":
            time_level = "month"
        elif time_level not in ["hour", "day", "month"]:
            raise ArgumentError("Can not drill down time to '%s'" % time_level)

        params["unit"] = time_level

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
                condition = self._point_condition(cut.dimension, cut.path[0])
                conditions.append(condition)
            elif isinstance(cut, RangeCut):
                condition = self._range_condition(cut.dimension,
                                                  cut.from_path[0],
                                                  cut.to_path[0])
                conditions.append(condition)
            elif isinstance(cut, SetCut):
                set_conditions = []
                for path in cut.paths:
                    condition = self._point_condition(cut.dimension, path[0])
                    set_conditions.append(condition)
                condition = " or ".join(set_conditions)
                conditions.append(condition)

        if len(conditions) > 1:
            conditions = ["(%s)" % cond for cond in conditions]
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

        # Assumption:
        #   mixpanel returns same time series structure for every request with
        #   same parameters => we can take one (any) response and share the
        #   series with other responses

        time_series = responses[measure_names[0]]["data"]["series"]
        time_series = [(key, time_to_path(key)) for key in time_series]

        time_levels = ["time."+level.name for level in drilldown["time"].levels]

        result_cells = []

        if not drilldown_on:
            measure_values = {}

            cells = {}

            for time_key, time_path in time_series:
                cells[time_key] = dict(zip(time_levels, time_path))

            for measure in measure_names:
                measure_response_values = responses[measure]["data"]["values"]
                measure_values = measure_response_values[self.cube.name]

                for time_key, time_path in time_series:
                    cell = cells[time_key]
                    cell[measure] = measure_values[time_key]
            
            items = cells.items()
            items.sort(lambda a, b: cmp(a[0], b[0]))
            result_cells = [ v for k, v in items ]

        else: # if drilldown_on
            # TODO: order keys

            # values: { city_A: {time:value, ...}, city_B: {time:value, ...} }
            drilldown_dim = drilldown_on.dimension.name

            # cells are ordered by time drill, then non-time drill

            for time_key, time_path in time_series:
                cells = {}

                cells[time_key] = {}
                time_cells = {}
                cells[time_key] = time_cells

                for measure in measure_names:
                    measure_values = responses[measure]["data"]["values"]

                    for dim_key, dim_values in measure_values.items():
                        cell = time_cells.setdefault(dim_key, dict(zip(time_levels, time_path)))
                        cell[drilldown_dim] = dim_key
                        if dim_values.has_key(time_key):
                            cell[measure]= dim_values[time_key]

                items = cells.items()
                items.sort(lambda a, b: cmp(a[0], b[0]))
                for cell_list in [ v.values() for k, v in items ]:
                    cell_list.sort(lambda a,b: cmp(a[drilldown_dim], b[drilldown_dim]))
                    result_cells += cell_list


        result.cells = result_cells
        result.levels = drilldown.levels_dictionary()

        return result

    def _property(self, dim):
        """Return correct property name from dimension."""
        dim = str(dim)
        return self.cube.mappings.get(dim, dim)

    def _point_condition(self, dim, value):
        """Returns a point cut for flat dimension `dim`"""

        condition = '(string(properties["%s"]) == "%s")' % \
                        (self._property(dim), str(value))
        return condition

    def _range_condition(self, dim, from_value, to_value):
        """Returns a point cut for flat dimension `dim`. Assumes number."""

        condition = '(number(properties["%s"]) >= %s and ' \
                    'number(properties["%s"]) <= %s)' % \
                        (self._property(dim), from_value,
                        self._property(dim), to_value)
        return condition

