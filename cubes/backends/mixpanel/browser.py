# -*- coding=utf -*-
from ...browser import *
from ...errors import *
from ...model import *
from ...common import get_logger
from .aggregator import _MixpanelResponseAggregator
from .utils import *

from .store import DEFAULT_TIME_HIERARCHY

import datetime
import calendar
from collections import OrderedDict, defaultdict

_measure_param = {
        "total": "general",
        "unique": "unique",
        "average": "average"
    }

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

        measures = measures or cube.measures 
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

        path_time_from = coalesce_date_path(path_time_from, 0, (time_cut.hierarchy if time_cut else None))
        path_time_to = coalesce_date_path(path_time_to, 1, (time_cut.hierarchy if time_cut else None))

        self.logger.debug(self.cube.__dict__)
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

        if time_level and time_level not in self.cube.dimension("time").level_names:
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

        labels = aggregator.time_levels[:]
        if drilldown_on:
            labels.append(drilldown_on.dimension.name)
        labels += measure_names
        result.labels = labels

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
