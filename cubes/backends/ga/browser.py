# -*-coding=utf -*-

from ...browser import *
from .mapper import GoogleAnalyticsMapper
from ...logging import get_logger
from ...calendar import Calendar

# Google Python API Documentation:
# https://developers.google.com/api-client-library/python/start/get_started

_DEFAULT_START_DATE = (2005, 1, 1)

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


def date_string(path, default_date):
    """Converts YMD path into a YYYY-MM-DD date."""
    # TODO: use Calendar

    path = path or []

    (year, month, day) = tuple(path + [0] * (3 - len(path)))

    year = int(year) or default_date[0]
    month = int(month) or default_date[1]
    day = int(day) or default_date[2]

    return "%04d-%02d-%02d" % (year, month, day)


class GoogleAnalyticsBrowser(AggregationBrowser):
    __extension_name__ = "ga"

    def __init__(self, cube, store, locale=None, **options):

        self.store = store
        self.cube = cube
        self.locale = locale
        self.logger = get_logger()
        self.logger.setLevel("DEBUG")
        self.mapper = GoogleAnalyticsMapper(cube, locale)

        # Note: Make sure that we have our own calendar copy, not workspace
        # calendar (we don't want to rewrite anything shared)
        self.calendar = Calendar(timezone=self.store.timezone)


        self.default_start_date = self.store.default_start_date \
                                        or _DEFAULT_START_DATE
        self.default_end_date = self.store.default_end_date

    def featuers(self):
        return {
            "actions": ["aggregate"]
        }

    def provide_aggregate(self, cell, aggregates, drilldown, split, order,
                          page, page_size, **options):

        aggregate_names = [a.name for a in aggregates]
        native_aggregates = [a for a in aggregates if not a.function]
        native_aggregate_names = [a.name for a in native_aggregates]

        result = AggregationResult(cell=cell, aggregates=aggregates,
                                   drilldown=drilldown)

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

        self.logger.debug("GA query: date from %s to %s, dims:%s metrics:%s"
                          % (start_date, end_date, dimensions, metrics))

        response = self.store.get_data(start_date=start_date,
                                       end_date=end_date,
                                       filters=filters,
                                       dimensions=dimensions,
                                       metrics=metrics,
                                       start_index=start_index,
                                       max_results=max_results)

        # TODO: remove this debug once satisfied
        import json
        print "=== RESPONSE:"
        print json.dumps(response, indent=4)

        attributes = dimension_attrs + aggregates
        labels = [attr.ref() for attr in attributes]
        rows = response["rows"]
        data_types = [ _type_func(c.get('dataType')) for c in response['columnHeaders'] ]

        rows = [ map(lambda i: i[0](i[1]), zip(data_types, row)) for row in rows ]
        if drilldown:
            result.cells = [dict(zip(labels, row)) for row in rows]
            # TODO: Use totalsForAllResults
            result.summary = None
        else:
            result.summary = dict(zip(labels, rows[0]))

        # Set the result cells iterator (required)
        result.labels = labels

        result.total_cell_count = response["totalResults"]

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
            from_path = None
            to_path = None
        else:
            if isinstance(cut, RangeCut):
                from_path = cut.from_path
                to_path = cut.to_path
            elif isinstance(cut, PointCut):
                from_path = cut.path
                to_path = cut.path
            else:
                raise ArgumentError("Unsupported time cut type %s"
                                    % str(type(cut)))

        units = ("year", "month", "day")
        start = date_string(from_path, self.default_start_date)

        if self.default_end_date:
            end = date_string(to_path, self.default_end_date)
        else:
            end = date_string(to_path, self.calendar.now_path(units))

        return (start, end)
