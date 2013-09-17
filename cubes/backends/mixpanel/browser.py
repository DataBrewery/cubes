from ...browser import *
from ...errors import *
from ...model import *

import datetime

def fix_time_path(path, defaults):
    if not path:
        return tuple(defaults)

    if len(path) == 1:
        return (path[0], defaults[1], defaults[2])
    elif len(path) == 2:
        return (path[0], path[1], defaults[2])
    else:
        return tuple(path)

class MixpanelBrowser(AggregationBrowser):
    def __init__(self, cube, store, locale=None, metadata=None, **options):
        self.store = store
        self.cube = cube
        self.options = options

    def aggregate(self, cell=None, measures=None, drilldown=None, split=None,
                    **options):

        if split:
            raise BrowserError("split in mixpanel is not supported")

        # TODO: this is incosistent with "if nothing explicit, then all"
        measures = measures or ["total"]
        measures = self.cube.get_measures(measures)

        cell = cell or Cell(self.cube)

        drilldown = levels_from_drilldown(cell, drilldown)
        dd_dimensions = [dd.dimension.name for dd in drilldown]

        time_count = dd_dimensions.count("time")

        if not time_count:
            raise ArgumentError("Time dimension drilldown is required for mixpanel")
        elif time_count > 1:
            raise ArgumentError("Time dimension specified more than once in drilldown")
        elif time_count == 1 and len(dd_dimensions) > 2:
            raise ArgumentError("Can not drill down with more than one "
                                "non-time dimension in mixpanel")


        #
        # Create from-to date range from time dimension cut
        #
        time_cut = cell.cut_for_dimension("time")
        if not time_cut:
            time_from_path = []
            time_to_path = []
        elif isinstance(time_cut, PointCut):
            time_from_path = time_cut.path or []
            time_to_path = time_cut.path or []
        elif isinstance(time_cut, RangeCut):
            time_from_path = time_cut.from_path or []
            time_to_path = time_cut.to_path or []
        else:
            raise ArgumentError("Mixpanel does not know how to handle cuts "
                                "of type %s" % type(time_cut))

        # Defaults:
        #     from date - first day of current month
        #     to date - today

        today = datetime.datetime.today()

        time_from_path = fix_time_path(time_from_path,
                                      [today.year, today.month, 1])
        time_to_path = fix_time_path(time_to_path,
                                     [today.year, today.month, today.day])

        params = {
                "event": self.cube.name,
                "from_date": ("%s-%s-%s" % time_from_path),
                "to_date": ("%s-%s-%s" % time_to_path)
            }

        # TODO: set "on" property to dd dimension
        # TODO: set "where" condition for cell

        if "limit" in options:
            params["limit"] = options["limit"]

        response = self.store.request(["segmentation"],
                                    params)

        result = AggregationResult(cell, measures)

        # TODO: get this
        # result.total_cell_count = None
        # TODO: compute summary

        values = response["data"]["values"][self.cube.name]
        cells = []
        for key in response["data"]["series"]:
            value = values[key]

            time_path = [int(v) for v in key.split("-")]
            value_cell = {
                    "time": time_path,
                    "total_sum": value
                }
            cells.append(value_cell)

        result.cells = cells

        return result
