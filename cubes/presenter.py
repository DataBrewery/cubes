# -*- coding=utf -*-
from .errors import *
from StringIO import StringIO
from .model import split_aggregate_ref
from .common import subclass_iterator, decamelize, to_identifier

try:
    import jinja2
except ImportError:
    from .common import MissingPackage
    jinja2 = MissingPackage("jinja2", "Templating engine")

__all__ = [
            "create_presenter",
            "register_presenter",
            "TextTablePresenter",
            "SimpleDataTablePresenter",
            "SimpleHTMLTablePresenter"
            ]

_presenters = {}

def register_presenter(presenter_type, factory):
    """Register presenter factory with type name `presenter_type`"""

    _presenters[presenter_type] = factory

def create_presenter(presenter_type, *args, **kwargs):
    """Create a presenter of type `presenter_type`"""
    global _presenters

    if not _presenters:
        _presenters = collect_subclasses(Presenter, "_presenter")

    try:
        presenter_factory = _presenters[presenter_type]
    except KeyError:
        raise CubesError("unknown presenter '%s'" % presenter_type)

    return presenter_factory(*args, **kwargs)

def _jinja_env():
    """Create and return cubes jinja2 environment"""
    loader = jinja2.PackageLoader('cubes', 'templates')
    env = jinja2.Environment(loader=loader)
    return env

class Presenter(object):
    """Empty class for the time being. Currently used only for finding all
    built-in subclasses"""
    pass

class TextTablePresenter(Presenter):
    def __init__(self, measure_format=None):
        super(TextTablePresenter, self).__init__()
        self.format = measure_format or {}

    def present(self, result, dimension, measures):
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


class SimpleDataTablePresenter(Presenter):
    def __init__(self, count_label=None, levels=None):
        """Creates a presenter that formats result into a tabular structure.
        `count_label` is default label to be used for `record_count`
        aggregation."""

        super(SimpleDataTablePresenter, self).__init__()
        self.count_label = count_label

    def present(self, result, dimension, aggregated_measures):

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

class SimpleHTMLTablePresenter(Presenter):
    def __init__(self, count_label=None, create_links=True,
                 table_style=None):
        """Create a simple HTML table presenter"""

        super(SimpleHTMLTablePresenter, self).__init__()

        self.env = _jinja_env()
        self.presenter = SimpleDataTablePresenter(count_label)
        self.template = self.env.get_template("simple_table.html")
        self.create_links = create_links
        self.table_style = table_style

    def present(self, result, dimension, aggregated_measures):
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

        table = self.presenter.present(result, dimension, aggregated_measures)

        output = self.template.render(cell=result.cell,
                                      dimension=dimension,
                                      table=table,
                                      create_links=self.create_links,
                                      table_style=self.table_style,
                                      is_last=is_last)
        return output

class RickshawSeriesPresenter(Presenter):
    """Presenter for series to be used in Rickshaw JavaScript charting
    library.

    Library URL: http://code.shutterstock.com/rickshaw/"""

    def present(self, result, aggregated_measure):
        data = []
        for x, row in enumerate(result):
            data.append({"x":x, "y":row[aggregated_measure]})
        return data

_default_ricshaw_palette = ["mediumorchid", "steelblue", "turquoise",
                            "mediumseagreen", "gold", "orange", "tomato"]

class RickshawMultiSeriesPresenter(Presenter):
    """Presenter for series to be used in Rickshaw JavaScript charting
    library.

    Library URL: http://code.shutterstock.com/rickshaw/"""

    def present(self, result, series_dimension, values_dimension,
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

