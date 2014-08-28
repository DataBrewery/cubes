# -*- coding: utf-8 -*-
from .compat import StringIO
from collections import namedtuple

from .extensions import Extensible, extensions
from .errors import *

try:
    import jinja2
except ImportError:
    from .common import MissingPackage
    jinja2 = MissingPackage("jinja2", "Templating engine")

__all__ = [
            "TextTableFormatter",
            "SimpleDataTableFormatter",
            "SimpleHTMLTableFormatter",
            "CrossTableFormatter",
            "HTMLCrossTableFormatter",
            "create_formatter"
            ]

def create_formatter(type_, *args, **kwargs):
    """Creates a formatter of type `type`. Passes rest of the arguments to the
    formatters initialization method."""
    return extensions.formatter(type_, *args, **kwargs)


def _jinja_env():
    """Create and return cubes jinja2 environment"""
    loader = jinja2.PackageLoader('cubes', 'templates')
    env = jinja2.Environment(loader=loader)
    return env


def parse_format_arguments(formatter, args, prefix="f:"):
    """Parses dictionary of `args` for formatter"""


class Formatter(Extensible):
    """Empty class for the time being. Currently used only for finding all
    built-in subclasses"""
    def __call__(self, *args, **kwargs):
        return self.format(*args, **kwargs)


class TextTableFormatter(Formatter):
    parameters = [
                {
                    "name": "aggregate_format",
                    "type": "string",
                    "label": "Aggregate format"
                },
                {
                    "name": "dimension",
                    "type": "string",
                    "label": "Dimension to drill-down by"
                },
                {
                    "name": "measures",
                    "type": "list",
                    "label": "list of measures"
                }
            ]

    mime_type = "text/plain"

    def __init__(self, aggregate_format=None):
        super(TextTableFormatter, self).__init__()
        self.agg_format = aggregate_format or {}

    def format(self, result, dimension, aggregates=None, hierarchy=None):
        cube = result.cell.cube
        aggregates = cube.get_aggregates(aggregates)

        rows = []
        label_width = 0
        aggregate_widths = [0] * len(aggregates)

        for row in result.table_rows(dimension, hierarchy=hierarchy):
            display_row = []
            label_width = max(label_width, len(row.label))
            display_row.append( (row.label, '<') )

            for i, aggregate in enumerate(aggregates):
                if aggregate.function in ["count", "count_nonempty"]:
                    default_fmt = "d"
                else:
                    default_fmt = ".2f"

                fmt = self.agg_format.get(aggregate.ref(), default_fmt)
                text = format(row.record[aggregate.ref()], fmt)
                aggregate_widths[i] = max(aggregate_widths[i], len(text))
                display_row.append( (text, '>') )
            rows.append(display_row)

        widths = [label_width] + aggregate_widths
        stream = StringIO()

        for row in rows:
            for i, fvalue in enumerate(row):
                value = fvalue[0]
                alignment = fvalue[1]
                text = format(value, alignment + "%ds" % (widths[i]+1))
                stream.write(text)
            stream.write("\n")

        value = stream.getvalue()
        stream.close()

        return value


class SimpleDataTableFormatter(Formatter):

    parameters = [
                {
                    "name": "dimension",
                    "type": "string",
                    "label": "dimension to consider"
                },
                {
                    "name": "aggregates",
                    "short_name": "aggregates",
                    "type": "list",
                    "label": "list of aggregates"
                }
            ]

    mime_type = "application/json"

    def __init__(self, levels=None):
        """Creates a formatter that formats result into a tabular structure.
        """

        super(SimpleDataTableFormatter, self).__init__()

    def format(self, result, dimension, hierarchy=None, aggregates=None):

        cube = result.cell.cube
        aggregates = cube.get_aggregates(aggregates)

        dimension = cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)
        cut = result.cell.cut_for_dimension(dimension)

        if cut:
            rows_level = hierarchy[cut.level_depth()+1]
        else:
            rows_level = hierarchy[0]

        is_last = hierarchy.is_last(rows_level)

        rows = []

        for row in result.table_rows(dimension):
            rheader = { "label":row.label,
                        "key":row.key}
            # Get values for aggregated measures
            data = [row.record[str(agg)] for agg in aggregates]
            rows.append({"header":rheader, "data":data, "is_base": row.is_base})

        labels = [agg.label or agg.name for agg in aggregates]

        hierarchy = dimension.hierarchy()
        header = [rows_level.label or rows_level.name]
        header += labels

        data_table = {
                "header": header,
                "rows": rows
                }

        return data_table;

class TextTableFormatter2(Formatter):
    parameters = [
                {
                    "name": "measure_format",
                    "type": "string",
                    "label": "Measure format"
                },
                {
                    "name": "dimension",
                    "type": "string",
                    "label": "dimension to consider"
                },
                {
                    "name": "measures",
                    "type": "list",
                    "label": "list of measures"
                }
            ]

    mime_type = "text/plain"

    def __init__(self):
        super(TextTableFormatter, self).__init__()

    def format(self, result, dimension, measures):
        cube = result.cube
        dimension = cube.dimension(dimension)

        if not result.has_dimension(dimension):
            raise CubesError("Result was not drilled down by dimension "
                             "'%s'" % str(dimension))

        raise NotImplementedError
        table_formatter = SimpleDataTableFormatter()

CrossTable = namedtuple("CrossTable", ["columns", "rows", "data"])

class CrossTableFormatter(Formatter):
    parameters = [
                {
                    "name": "aggregates_on",
                    "type": "string",
                    "label": "Localtion of aggregates. Can be columns, rows or "
                             "cells",
                    "scope": "formatter",
                },
                {
                    "name": "onrows",
                    "type": "attributes",
                    "label": "List of dimension attributes to be put on rows"
                },
                {
                    "name": "oncolumns",
                    "type": "attributes",
                    "label": "List of attributes to be put on columns"
                },
                {
                    "name": "aggregates",
                    "short_name": "aggregates",
                    "type": "list",
                    "label": "list of aggregates"
                }
            ]

    mime_type = "application/json"

    def __init__(self, aggregates_on=None):
        """Creates a cross-table formatter.

        Arguments:

        * `aggregates_on` – specify how to put aggregates in the table. Might
          be one of ``rows``, ``columns`` or ``cells`` (default).

        If aggregates are put on rows or columns, then respective row or
        column is added per aggregate. The data contains single aggregate
        values.

        If aggregates are put in the table as cells, then the data contains
        tuples of aggregates in the order as specified in the `aggregates`
        argument of `format()` method.
        """

        super(CrossTableFormatter, self).__init__()

        self.aggregates_on = aggregates_on

    def format(self, result, onrows=None, oncolumns=None, aggregates=None,
               aggregates_on=None):
        """
        Creates a cross table from a drilldown (might be any list of records).
        `onrows` contains list of attribute names to be placed at rows and
        `oncolumns` contains list of attribute names to be placet at columns.
        `aggregates` is a list of aggregates to be put into cells. If
        aggregates are not specified, then only ``record_count`` is used.

        Returns a named tuble with attributes:

        * `columns` - labels of columns. The tuples correspond to values of
          attributes in `oncolumns`.
        * `rows` - labels of rows as list of tuples. The tuples correspond to
          values of attributes in `onrows`.
        * `data` - list of aggregate data per row. Each row is a list of
          aggregate tuples.

        """

        # Use formatter's default, if set
        aggregates_on = aggregates_on or self.aggregates_on
        cube = result.cell.cube
        aggregates = cube.get_aggregates(aggregates)

        matrix = {}
        row_hdrs = []
        column_hdrs = []

        labels = [agg.label for agg in aggregates]
        agg_refs = [agg.ref() for agg in aggregates]

        if aggregates_on is None or aggregates_on == "cells":
            for record in result.cells:
                # Get table coordinates
                hrow = tuple(record[f] for f in onrows)
                hcol = tuple(record[f] for f in oncolumns)

                if not hrow in row_hdrs:
                    row_hdrs.append(hrow)
                if not hcol in column_hdrs:
                    column_hdrs.append(hcol)

                matrix[(hrow, hcol)] = tuple(record[a] for a in agg_refs)

        else:
            for record in result.cells:
                # Get table coordinates
                base_hrow = [record[f] for f in onrows]
                base_hcol = [record[f] for f in oncolumns]

                for i, agg in enumerate(aggregates):

                    if aggregates_on == "rows":
                        hrow = tuple(base_hrow + [agg.label or agg.name])
                        hcol = tuple(base_hcol)

                    elif aggregates_on == "columns":
                        hrow = tuple(base_hrow)
                        hcol = tuple(base_hcol + [agg.label or agg.name])

                    if not hrow in row_hdrs:
                        row_hdrs.append(hrow)

                    if not hcol in column_hdrs:
                        column_hdrs.append(hcol)

                    matrix[(hrow, hcol)] = record[agg.ref()]

        data = []

        for hrow in row_hdrs:
            row = [matrix.get((hrow, hcol)) for hcol in column_hdrs]
            data.append(row)

        return CrossTable(column_hdrs, row_hdrs, data)

class HTMLCrossTableFormatter(CrossTableFormatter):
    parameters = [
                {
                    "name": "aggregates_on",
                    "type": "string",
                    "label": "Localtion of measures. Can be columns, rows or "
                             "cells",
                    "scope": "formatter",
                },
                {
                    "name": "onrows",
                    "type": "attributes",
                    "label": "List of dimension attributes to be put on rows"
                },
                {
                    "name": "oncolumns",
                    "type": "attributes",
                    "label": "List of attributes to be put on columns"
                },
                {
                    "name": "aggregates",
                    "short_name": "aggregates",
                    "type": "list",
                    "label": "list of aggregates"
                },
                {
                    "name": "table_style",
                    "description": "CSS style for the table"
                }
            ]
    mime_type = "text/html"

    def __init__(self, aggregates_on="cells", measure_labels=None,
            aggregation_labels=None, measure_label_format=None,
            count_label=None, table_style=None):
        """Create a simple HTML table formatter. See `CrossTableFormatter` for
        information about arguments."""

        if aggregates_on not in ["columns", "rows", "cells"]:
            raise ArgumentError("aggregates_on sohuld be either 'columns' "
                                "or 'rows', is %s" % aggregates_on)

        super(HTMLCrossTableFormatter, self).__init__(aggregates_on)

        self.env = _jinja_env()
        self.template = self.env.get_template("cross_table.html")
        self.table_style = table_style

    def format(self, result, onrows=None, oncolumns=None, aggregates=None):

        table = super(HTMLCrossTableFormatter, self).format(result,
                                                        onrows=onrows,
                                                        oncolumns=oncolumns,
                                                        aggregates=aggregates)
        output = self.template.render(table=table,
                                      table_style=self.table_style)
        return output


class SimpleHTMLTableFormatter(Formatter):

    parameters = [
                {
                    "name": "dimension",
                    "type": "string",
                    "label": "dimension to consider"
                },
                {
                    "name": "aggregates",
                    "short_name": "aggregates",
                    "type": "list",
                    "label": "list of aggregates"
                }
            ]

    mime_type = "text/html"

    def __init__(self, create_links=True, table_style=None):
        """Create a simple HTML table formatter"""

        super(SimpleHTMLTableFormatter, self).__init__()

        self.env = _jinja_env()
        self.formatter = SimpleDataTableFormatter()
        self.template = self.env.get_template("simple_table.html")
        self.create_links = create_links
        self.table_style = table_style

    def format(self, result, dimension, aggregates=None, hierarchy=None):
        cube = result.cell.cube
        dimension = cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)
        aggregates = cube.get_aggregates(aggregates)

        cut = result.cell.cut_for_dimension(dimension)

        if cut:
            is_last = cut.level_depth() >= len(hierarchy)
        else:
            is_last = False

        table = self.formatter.format(result, dimension, aggregates=aggregates)

        output = self.template.render(cell=result.cell,
                                      dimension=dimension,
                                      table=table,
                                      create_links=self.create_links,
                                      table_style=self.table_style,
                                      is_last=is_last)
        return output

class RickshawSeriesFormatter(Formatter):
    """Presenter for series to be used in Rickshaw JavaScript charting
    library.

    Library URL: http://code.shutterstock.com/rickshaw/"""

    def format(self, result, aggregate):
        data = []
        for x, row in enumerate(result):
            data.append({"x":x, "y":row[str(aggregate)]})
        return data

_default_ricshaw_palette = ["mediumorchid", "steelblue", "turquoise",
                            "mediumseagreen", "gold", "orange", "tomato"]

class RickshawMultiSeriesFormatter(Formatter):
    """Presenter for series to be used in Rickshaw JavaScript charting
    library.

    Library URL: http://code.shutterstock.com/rickshaw/"""

    def format(self, result, series_dimension, values_dimension,
                aggregate, color_map=None, color_palette=None):
        """Provide multiple series. Result is expected to be ordered.

        Arguments:
            * `result` – AggregationResult object
            * `series_dimension` – dimension used for split to series
            * `value_dimension` – dimension used to get values
            * `aggregated_measure` – measure attribute to be plotted
            * `color_map` – The dictionary is a map between dimension keys and
              colors, the map keys should be strings.
            * `color_palette` – List of colors that will be cycled for each
              series.

        Note: you should use either color_map or color_palette, not both.
        """

        if color_map and color_palette:
            raise CubesError("Use either color_map or color_palette, not both")

        color_map = color_map or {}
        color_palette = color_palette or _default_ricshaw_palette

        cube = result.cell.cube
        series_dimension = cube.dimension(series_dimension)
        values_dimension = cube.dimension(values_dimension)
        try:
            series_level = result.levels[str(series_dimension)][-1]
        except KeyError:
            raise CubesError("Result was not drilled down by dimension '%s'" \
                                % str(series_dimension))
        try:
            values_level = result.levels[str(values_dimension)][-1]
        except KeyError:
            raise CubesError("Result was not drilled down by dimension '%s'" \
                                % str(values_dimension))
        series = []
        rows = [series_level.key.ref(), series_level.label_attribute.ref()]
        columns = [values_level.key.ref(), values_level.label_attribute.ref()]

        cross_table = result.cross_table(onrows=rows,
                                         oncolumns=columns,
                                         aggregates=[aggregate])

        color_index = 0

        for head, row in zip(cross_table.rows, cross_table.data):
            data = []
            for x, value in enumerate(row):
                data.append({"x":x, "y":value[0]})

            # Series label is in row heading at index 1
            series_dict = {
                            "data": data,
                            "name": head[1]
                          }
            # Use dimension key for color
            if color_map:
                series_dict["color"] = color_map.get(str(head[0]))
            elif color_palette:
                color_index = (color_index + 1) % len(color_palette)
                series_dict["color"] = color_palette[color_index]

            series.append(series_dict)

        return series

