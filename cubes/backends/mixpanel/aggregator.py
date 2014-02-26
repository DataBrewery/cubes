# -*- coding=utf -*-
from ...browser import *
from ...errors import *
from ...model import *

from .store import DEFAULT_TIME_HIERARCHY
from .utils import *

from collections import defaultdict
from datetime import datetime
import pytz

class _MixpanelResponseAggregator(object):
    def __init__(self, browser, responses, aggregate_names, drilldown, split,
                    actual_time_level):
        """Aggregator for multiple mixpanel responses (multiple dimensions)
        with drill-down post-aggregation.

        Arguments:

        * `browser` – owning browser
        * `reposnes` – mixpanel responses by `measure_names`
        * `aggregate_names` – list of collected measures
        * `drilldown` – a `Drilldown` object from the browser aggregation
          query
        * `split` - a split Cell object from the browser aggregation query

        Object attributes:

        * `aggregate_names` – list of measure names from the response
        * `aggregate_data` – a dictionary where keys are measure names and
          values are actual data points.

        * `time_cells` – an ordered dictionary of collected cells from the
          response. Key is time path, value is cell contents without the time
          dimension.
        """
        self.browser = browser
        self.logger = browser.logger
        self.drilldown = drilldown
        self.aggregate_names = aggregate_names
        self.actual_time_level = actual_time_level

        # Extract the data
        self.aggregate_data = {}
        for aggregate in aggregate_names:
            self.aggregate_data = responses[aggregate]["data"]["values"]

        # Get time drilldown levels, if we are drilling through time
        time_drilldowns = drilldown.drilldown_for_dimension("time")

        if time_drilldowns:
            time_drilldown = time_drilldowns[0]
            self.last_time_level = str(time_drilldown.levels[-1])
            self.time_levels = ["time."+str(l) for l in time_drilldown.levels]
            self.time_hierarchy = str(time_drilldown.hierarchy)
        else:
            time_drilldown = None
            self.last_time_level = None
            self.time_levels = []
            self.time_hierarchy = DEFAULT_TIME_HIERARCHY

        self.drilldown_on = None
        for obj in drilldown:
            if obj.dimension.name != "time":
                # this is a DrilldownItem object. represent it as 'dim.level' or just 'dim' if flat
                self.drilldown_on = ( "%s.%s" % (obj.dimension.name, obj.levels[-1].name) ) if ( not obj.dimension.is_flat ) else obj.dimension.name
                self.drilldown_on_value_func = lambda x: x

        if self.drilldown_on is None and split:
            self.drilldown_on = SPLIT_DIMENSION_NAME
            self.drilldown_on_value_func = lambda x: True if x == "true" else False

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

        for aggregate in self.aggregate_names:
            self._collect_aggregate_cells(aggregate)

    def _collect_aggregate_cells(self, aggregate):
        """Collects the cells from the response in a time series dictionary
        `time_cells` where keys are tuples: `(time_path, group)`. `group` is
        drill-down key value for the cell, such as `New York` for `city`."""

        # Note: For no-drilldown this would be only one pass and group will be
        # a cube name

        # TODO: To add multiple drill-down dimensions in the future, add them
        # to the `group` part of the key tuple

        for group_key, group_series in self.aggregate_data.items():

            for time_key, value in group_series.items():
                time_path = time_to_path(time_key, self.last_time_level,
                                                        self.time_hierarchy)
                key = (time_path, group_key)

                # self.logger.debug("adding cell %s" % (key, ))
                cell = self.time_cells.setdefault(key, {})
                cell[aggregate] = value

                # FIXME: do this only on drilldown
                if self.drilldown_on:
                    cell[self.drilldown_on] = group_key

    def _reduce_cells(self):
        """Reduce the cells according to the time dimensions."""

        def reduce_cell(result, cell):
            # We assume only _sum aggergation
            # All measures should be prepared so we can to this
            for aggregate in self.aggregate_names:
                result[aggregate] = result.get(aggregate, 0) + \
                                   cell.get(aggregate, 0)
            return result

        # 1. Map cells to reduced time path
        #
        reduced_map = defaultdict(list)
        reduced_len = len(self.time_levels)

        for key, cell in self.time_cells.items():
            time_path = key[0]
            reduced_path = time_path[0:reduced_len]

            reduced_key = (reduced_path, key[1])

            # self.logger.debug("reducing %s -> %s" % (key, reduced_key))
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

        # compute the current datetime, convert to path
        current_time_path = time_to_path(
                pytz.timezone('UTC').localize(datetime.utcnow()).astimezone(self.browser.timezone).strftime("%Y-%m-%d %H:00:00"), 
                self.last_time_level, 
                self.time_hierarchy)

        self.cells = []
        for key, cell in cells:
            # If we are aggregating at finer granularity than "all":
            time_key = key[0]
            if time_key:
                # if time_key ahead of current time path, discard
                if time_key > current_time_path:
                    continue
                cell.update(zip(self.time_levels, time_key))

            # append the drilldown_on attribute ref
            if self.drilldown_on:
                cell[self.drilldown_on] = self.drilldown_on_value_func(key[1])

            self.cells.append(cell)

