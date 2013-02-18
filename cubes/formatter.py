# -*- coding=utf -*-
from .errors import *
from StringIO import StringIO
from .model import split_aggregate_ref
from .common import collect_subclasses, decamelize, to_identifier
from collections import namedtuple

try:
    import jinja2
except ImportError:
    from .common import MissingPackage
    jinja2 = MissingPackage("jinja2", "Templating engine")

__all__ = [
            "create_formatter",
            "register_formatter",
            "TextTableFormatter",
            "SimpleDataTableFormatter",
            "SimpleHTMLTableFormatter",
            "CrossTableFormatter",
            "HTMLCrossTableFormatter"
            ]

_formatters = {}

def register_formatter(formatter_type, factory):
    """Register formatter factory with type name `formatter_type`"""

    _formatters[formatter_type] = factory

def create_formatter(formatter_type, convert_options=False, **options):
    """Create a formatter of type `formatter_type` with initialization
    `options`.

    If `convert_values` is ``True`` then values are considered to be
    strings and are converted into their respective types as specified in
    the formatter metadata. This should be used as convenience conversion
    from web server, for example.
    """
    global _formatters

    if not _formatters:
        _formatters = collect_subclasses(Formatter, "_formatter")

    try:
        formatter_factory = _formatters[formatter_type]
    except KeyError:
        raise CubesError("unknown formatter '%s'" % formatter_type)

    if convert_options:
        options = convert_formatter_options(formatter_factory, options)

    return formatter_factory(**options)

def create_formatters(description, convert_options=False):
    """Initialize formatters from `description` dictionary where keys are
    formatter identifiers used in reports and values are formatter options
    passed to the formatter's initialization method.

    By default formatter of the same type as contents of the identifier
    string is created. You can specify formatter type in ``type`` key of
    the formatter options. For example:

    .. code-block: javascript

        {
            "csv": { "delimiter": "|" },
            "csv_no_headers": {"type":"csv", "headers": False}
        }

    Returns a dictionary with formatter identifiers as keys and formatter
    instances as values.

    Use this method to create dictionary of formatters from a configuration
    file, web server configuration, database or any other user facing
    application that does not require (or does not allow) Python to be used by
    users.
    """

    formatters = {}

    for name, options in config:
        if "type" in options:
            formatter_type = options["type"]
            options = dict(options)
            del options["type"]
        else:
            formatter_type = name

        formatter = create_formatter(name,
                                     convert_options=convert_options,
                                     **options)
        formatters[name] = formatter

    return formatters


def convert_formatter_options(formatter, options):
    """Convert options according to type specification of formatter
    parameters."""
    new_options = {}

    parameters = {}
    for parameter in formatter.parameters:
        parameters[parameter["name"]] = parameter
        if "short_name" in "parameter":
            parameters[parameter["short_name"]] = parameter

    for key, string_value in options:
        try:
            parameter = parameters[key]
        except KeyError:
            raise ArgumentError("Unknown parameter %s for formatter %s" %
                                                    (key, formatter_type))
        value_type = parameter.get("type", "string")
        value = string_to_value(string_value, parameter_type, key)
        new_options[key] = value

    return new_options

def _jinja_env():
    """Create and return cubes jinja2 environment"""
    loader = jinja2.PackageLoader('cubes', 'templates')
    env = jinja2.Environment(loader=loader)
    return env

def parse_format_arguments(formatter, args, prefix="f:"):
    """Parses dictionary of `args` for formatter"""


class Formatter(object):
    """Empty class for the time being. Currently used only for finding all
    built-in subclasses"""
    pass

class TextTableFormatter(Formatter):
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

    def __init__(self, measure_format=None):
        super(TextTableFormatter, self).__init__()
        self.format = measure_format or {}

    def format(self, result, dimension, measures):
        rows = []
        label_width = 0
        measure_widths = [0] * len(measures)

        for row in result.table_rows(dimension):
            display_row = []
            label_width = max(label_width, len(row.label))
            display_row.append( (row.label, '<') )
            for i, measure in enumerate(measures):
                if measure == "record_count":
                    default_fmt = "d"
                else:
                    default_fmt = ".2f"

                fmt = self.format.get(measure, default_fmt)
                text = format(row.record[measure], fmt)
                measure_widths[i] = max(measure_widths[i], len(text))
                display_row.append( (text, '>') )
            rows.append(display_row)

        widths = [label_width] + measure_widths
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
                    "name": "count_label",
                    "type": "string",
                    "label": "Label of record count column"
                },
                {
                    "name": "dimension",
                    "type": "string",
                    "label": "dimension to consider"
                },
                {
                    "name": "aggregated_measures",
                    "short_name": "measures",
                    "type": "list",
                    "label": "list of measures"
                }
            ]

    mime_type = "application/json"

    def __init__(self, count_label=None, levels=None):
        """Creates a formatter that formats result into a tabular structure.
        `count_label` is default label to be used for `record_count`
        aggregation."""

        super(SimpleDataTableFormatter, self).__init__()
        self.count_label = count_label

    def format(self, result, dimension, aggregated_measures):

        cube = result.cell.cube
        dimension = cube.dimension(dimension)
        cut = result.cell.cut_for_dimension(dimension)

        if cut:
            path = cut.path
            hierarchy = dimension.hierarchy(cut.hierarchy)
        else:
            path = []
            hierarchy = dimension.hierarchy()

        levels = hierarchy.levels_for_path(path)
        if levels:
            rows_level = hierarchy.next_level(levels[-1])
        else:
            rows_level = hierarchy.next_level(None)

        is_last = hierarchy.is_last(rows_level)

        rows = []

        for row in result.table_rows(dimension):
            rheader = { "label":row.label,
                        "key":row.key}
            # Get values for aggregated measures
            data = [row.record[m] for m in aggregated_measures]
            rows.append({"header":rheader, "data":data, "is_base": row.is_base})

        # Create column headings
        measures = [split_aggregate_ref(m) for m in aggregated_measures]
        # FIXME: we should format the measure with aggregate here

        labels = []
        for (measure, aggregation) in measures:
            if measure != "record_count":
                attr = cube.measure(measure)
                label = attr.label or attr.name
            else:
                label = self.count_label or "Count"
            labels.append(label)

        hierarchy = dimension.hierarchy()
        header = [rows_level.label or rows_level.name]
        header += labels

        data_table = {
                "header": header,
                "rows": rows
                }
        return data_table;

class TextTableFormatter(Formatter):
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

    def __init__(self, measure_format=None):
        super(TextTableFormatter, self).__init__()
        self.format = measure_format or {}

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
                    "name": "measures_as",
                    "type": "string",
                    "label": "Localtion of measures. Can be columns, rows or "
                             "cells",
                    "scope": "formatter",
                },
                {
                    "name": "count_label",
                    "type": "string",
                    "label": "Label to be used for record_count measure",
                    "scopr": "formatter"
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
                    "name": "measures",
                    "short_name": "measures",
                    "type": "list",
                    "label": "list of aggregated measures"
                }
            ]

    mime_type = "application/json"

    def __init__(self, measures_as=None, measure_labels=None,
            aggregation_labels=None, measure_label_format=None,
            count_label=None):
        """Creates a cross-table formatter.

        Arguments:

        * `measures_as` – specify how to put measures in the table. Might be
          one of ``rows``, ``columns`` or ``cells`` (default).
        * `measure_labels` – dictionary of labels to be used for measures
        * `aggregation_labels` – dictionary of labels of aggregations, used
          for default measure labeling
        * `measure_label_format` – format string for measure label, default is
          ``{measure} ({aggregation})``
        * `count_label` – label to be used for record count. Overrides
          default setting

        If measures are put on rows or columns, then respective row or column
        is added per measure. The data contains single measure values.

        If measures are put in the table as cells, then the data contains
        tuples of measures in the order as specified in the `measures`
        argument of `format()` method.

        If no `measure_labels` is provided or no key for a measure is found in
        the dictionary, then the label is constructect with form: "Measure
        (aggregation)", for example: "Amount (sum)".

        If `aggregation_labels` is provided, then it is used to give measure
        aggregation label.
        """
        super(CrossTableFormatter, self).__init__()

        self.measures_as = measures_as
        self.measure_labels = measure_labels or {}
        self.aggregation_labels = aggregation_labels or {}
        self.measure_label_format = measure_label_format or "{measure} ({aggregation})"
        self.count_label = count_label

    def format(self, result, onrows=None, oncolumns=None, measures=None,
               measures_as=None):
        """
        Creates a cross table from a drilldown (might be any list of records).
        `onrows` contains list of attribute names to be placed at rows and
        `oncolumns` contains list of attribute names to be placet at columns.
        `measures` is a list of measures to be put into cells. If measures are not
        specified, then only ``record_count`` is used.

        Returns a named tuble with attributes:

        * `columns` - labels of columns. The tuples correspond to values of
          attributes in `oncolumns`.
        * `rows` - labels of rows as list of tuples. The tuples correspond to
          values of attributes in `onrows`.
        * `data` - list of measure data per row. Each row is a list of measure
          tuples.

        """

        # Use formatter's default, if set
        measures_as = measures_as or self.measures_as
        cube = result.cell.cube

        matrix = {}
        row_hdrs = []
        column_hdrs = []

        measures = measures or ["record_count"]

        measure_labels = []
        for agg_measure in measures:
            if agg_measure != "record_count":
                # Try to get label from measure_labels
                label = self.measure_labels.get(agg_measure)

                # Construct a label if not provided
                if not label:
                    name, agg = split_aggregate_ref(agg_measure)
                    measure = cube.measure(name)

                    agg_label = self.aggregation_labels.get(agg, agg)
                    m_label = measure.label or measure.name

                    args = {"measure":m_label, "aggregation":agg_label}
                    label = self.measure_label_format.format(**args)
            else:
                measure = cube.measure("record_count")
                label = self.count_label or measure.label or str(measure)

            measure_labels.append(label)

        if measures_as is None or measures_as == "cells":
            for record in result.cells:
                # Get table coordinates
                hrow = tuple(record[f] for f in onrows)
                hcol = tuple(record[f] for f in oncolumns)

                if not hrow in row_hdrs:
                    row_hdrs.append(hrow)
                if not hcol in column_hdrs:
                    column_hdrs.append(hcol)

                matrix[(hrow, hcol)] = tuple(record[m] for m in measures)

        else:
            for record in result.cells:
                # Get table coordinates
                base_hrow = [record[f] for f in onrows]
                base_hcol = [record[f] for f in oncolumns]

                for i, measure in enumerate(measures):
                    measure_label = measure_labels[i]
                    if measures_as == "rows":
                        hrow = tuple(base_hrow + [measure_label])
                        hcol = tuple(base_hcol)
                    elif measures_as == "columns":
                        hrow = tuple(base_hrow)
                        hcol = tuple(base_hcol + [measure_label])

                    if not hrow in row_hdrs:
                        row_hdrs.append(hrow)
                    if not hcol in column_hdrs:
                        column_hdrs.append(hcol)

                    matrix[(hrow, hcol)] = record[measure]

        data = []

        for hrow in row_hdrs:
            row = [matrix.get((hrow, hcol)) for hcol in column_hdrs]
            data.append(row)

        return CrossTable(column_hdrs, row_hdrs, data)

class HTMLCrossTableFormatter(CrossTableFormatter):
    parameters = [
                {
                    "name": "measures_as",
                    "type": "string",
                    "label": "Localtion of measures. Can be columns, rows or "
                             "cells",
                    "scope": "formatter",
                },
                {
                    "name": "count_label",
                    "type": "string",
                    "label": "Label to be used for record_count measure",
                    "scopr": "formatter"
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
                    "name": "measures",
                    "short_name": "measures",
                    "type": "list",
                    "label": "list of aggregated measures"
                },
                {
                    "name": "table_style",
                    "description": "CSS style for the table"
                }
            ]
    mime_type = "text/html"

    def __init__(self, measures_as=None, measure_labels=None,
            aggregation_labels=None, measure_label_format=None,
            count_label=None, table_style=None):
        """Create a simple HTML table formatter. See `CrossTableFormatter` for
        information about arguments."""

        if measures_as not in ["columns", "rows"]:
            raise ArgumentError("measures_as sohuld be either 'columns' "
                                "or 'rows', is %s" % measures_as)

        super(HTMLCrossTableFormatter, self).__init__(measures_as=measures_as,
                                                measure_labels=measure_labels,
                                                aggregation_labels=aggregation_labels,
                                                measure_label_format=measure_label_format,
                                                count_label=count_label)

        self.env = _jinja_env()
        self.template = self.env.get_template("cross_table.html")
        self.table_style = table_style

    def format(self, result, onrows=None, oncolumns=None, measures=None):

        table = super(HTMLCrossTableFormatter, self).format(result,
                                                        onrows=onrows,
                                                        oncolumns=oncolumns,
                                                        measures=measures)
        output = self.template.render(table=table,
                                      table_style=self.table_style)
        return output


class SimpleHTMLTableFormatter(Formatter):

    parameters = [
                {
                    "name": "count_label",
                    "type": "string",
                    "label": "Label of record count column"
                },
                {
                    "name": "dimension",
                    "type": "string",
                    "label": "dimension to consider"
                },
                {
                    "name": "aggregated_measures",
                    "short_name": "measures",
                    "type": "list",
                    "label": "list of measures"
                }
            ]

    mime_type = "text/html"

    def __init__(self, count_label=None, create_links=True,
                 table_style=None):
        """Create a simple HTML table formatter"""

        super(SimpleHTMLTableFormatter, self).__init__()

        self.env = _jinja_env()
        self.formatter = SimpleDataTableFormatter(count_label)
        self.template = self.env.get_template("simple_table.html")
        self.create_links = create_links
        self.table_style = table_style

    def format(self, result, dimension, aggregated_measures):
        cube = result.cell.cube
        dimension = cube.dimension(dimension)
        cut = result.cell.cut_for_dimension(dimension)

        if cut:
            path = cut.path
            hierarchy = dimension.hierarchy(cut.hierarchy)
        else:
            path = []
            hierarchy = dimension.hierarchy()

        is_last = len(path)+1 >= len(hierarchy)

        table = self.formatter.format(result, dimension, aggregated_measures)

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

    def format(self, result, aggregated_measure):
        data = []
        for x, row in enumerate(result):
            data.append({"x":x, "y":row[aggregated_measure]})
        return data

_default_ricshaw_palette = ["mediumorchid", "steelblue", "turquoise",
                            "mediumseagreen", "gold", "orange", "tomato"]

class RickshawMultiSeriesFormatter(Formatter):
    """Presenter for series to be used in Rickshaw JavaScript charting
    library.

    Library URL: http://code.shutterstock.com/rickshaw/"""

    def format(self, result, series_dimension, values_dimension,
                aggregated_measure,
                color_map=None, color_palette=None):
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

        cross_table = result.cross_table(onrows=rows, oncolumns=columns,
                                         measures = [aggregated_measure])

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

