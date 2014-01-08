# -*-coding=utf -*-

from ...browser import *
from .mapper import GoogleAnalyticsMapper
from ...logging import get_logger

# Google Python API Documentation:
# https://developers.google.com/api-client-library/python/start/get_started

_REFERENCE_DATE = (2013, 1, 1)

_TYPE_FUNCS = {
    'STRING': str,
    'INTEGER': int,
    'FLOAT': float,
    'PERCENT': lambda x: float(x) / 100.0,
    'TIME': float
}

def _type_func(ga_datatype):
    if ga_datatype is None:
        ga_datatype = 'STRING'
    return _TYPE_FUNCS.get(ga_datatype.upper(), str)

def path_to_date(path):
    """Converts YMD path into a YYYY-MM-DD date."""
    # TODO: use Calendar

    (year, month, day) = tuple(path + [0]*(3-len(path)))

    year = int(year) or _REFERENCE_DATE[0]
    month = int(month) or _REFERENCE_DATE[1]
    day = int(day) or _REFERENCE_DATE[2]

    return "%04d-%02d-%02d" % (year, month, day)

class GoogleAnalyticsBrowser(AggregationBrowser):
    __identifier__ = "ga"

    def __init__(self, cube, store, locale=None, **options):

        self.store = store
        self.cube = cube
        self.locale = locale
        self.logger = get_logger()
        self.logger.setLevel("DEBUG")
        self.mapper = GoogleAnalyticsMapper(cube, locale)

    def featuers(self):
        return {
            "actions": ["aggregate"]
        }

    def aggregate(self, cell=None, measures=None, aggregates=None,
                  drilldown=None, split=None, order=None,
                  page=None, page_size=None, **options):

        if measures:
            raise ArgumentError("Google Analytics does not provide non-aggregated "
                                "measures")

        aggregates = self.prepare_aggregates(aggregates)

        aggregate_names = [a.name for a in aggregates]
        native_aggregates = [a for a in aggregates if not a.function]
        native_aggregate_names = [a.name for a in native_aggregates]

        # Get the cell and prepare cut parameters
        cell = cell or Cell(self.cube)

        drilldown = Drilldown(drilldown, cell)
        order = self.prepare_order(order, is_aggregate=True)

        result = AggregationResult(cell=cell, aggregates=aggregates)
        result.levels = drilldown.result_levels()

        #
        # Prepare the request:
        #
        filters = self.condition_for_cell(cell)
        start_date, end_date = self.time_condition_for_cell(cell)

        # Prepare drilldown:
        dimension_attrs = []
        for item in drilldown:
            dimension_attrs += [l.key for l in item.levels]

        refs = [self.mapper.physical(attr) for attr in dimension_attrs]
        dimensions = ",".join(refs)

        metrics = [self.mapper.physical(a) for a in aggregates]
        metrics = ",".join(metrics)

        if page is not None and page_size is not None:
            max_results = page_size
            start_index = (page * page_size) + 1
        else:
            max_results = None
            start_index = None

        response = self.store.get_data(
                start_date=start_date,
                end_date=end_date,
                filters=filters,
                dimensions=dimensions,
                metrics=metrics,
                start_index=start_index,
                max_results=max_results
                )

        import json
        print "=== RESPONSE:"
        print json.dumps(response, indent=4)

        attributes = dimension_attrs + aggregates
        labels = [attr.ref() for attr in attributes]
        rows = response["rows"]
        data_types = [ _type_func(c.get('dataType')) for c in response['columnHeaders'] ]
        rows = [ map(lambda i: i[0](i[1]), zip(data_types, row)) for row in rows ]

        result.cells = [dict(zip(labels, row)) for row in rows]

        # Set the result cells iterator (required)
        result.labels = labels

        result.total_cell_count = response["totalResults"]
        # TODO: Use totalsForAllResults
        result.summary = None

        return result

    def condition_for_cell(self, cell):
        conditions = []

        for cut in cell.cuts:
            if str(cut.dimension) == "time":
                continue

            # TODO: we consider GA dims to be flat
            dim = self.mapper.physical(cut.dimension.all_attributes[0])

            if isinstance(cut, PointCut):
                condition = "%s%s%s" % (dim, "!=" if cut.invert else "==", cut.path[0])
            elif isinstance(cut, RangeCut):

                if cut.from_path:
                    cond_from = "%s%s%s" % (dim, "<" if cut.invert else ">=", cut.from_path[0])
                else:
                    cond_from = None

                if cut.to_path:
                    cond_to = "%s%s%s" % (dim, ">" if cut.invert else "<=", cut.to_path[0])
                else:
                    cond_to = None

                if cond_from and cond_to:
                    condition = "%s;%s" % (cond_to, cond_from)
                else:
                    condition = cond_to or cond_from

            elif isinstance(cut, SetCut):
                sublist = []
                for value in cut.paths:
                    cond = "%s%s%s" % (dim, "!=" if cut.invert else "==", value)
                    sublist.append(cond)
                condition = ",".join(sublist)

            conditions.append(condition)

        if conditions:
            return ";".join(conditions)
        else:
            return None

    def time_condition_for_cell(self, cell):
        cut = cell.cut_for_dimension("time")
        if not cut:
            self.logger.debug("Using default time range for last month")
            raise NotImplementedError("No time dim specified, not handled yet")

        if isinstance(cut, RangeCut):
            start = path_to_date(cut.from_path)
            end = path_to_date(cut.to_path)
        elif isinstance(cut, PointCut):
            start = path_to_date(cut.path)
            end = start
        else:
            raise ArgumentError("Unsupported time cut type %s"
                                % str(type(cut)))

        return (start, end)
