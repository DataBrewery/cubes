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
            "collect_presenters",
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
        _presenters = collect_presenters()

    try:
        presenter_factory = _presenters[presenter_type]
    except KeyError:
        raise CubesError("unknown presenter '%s'" % presenter_type)

    return presenter_factory(*args, **kwargs)

def collect_presenters():
    """Collect all subclasses of Presenter and return a dictionary where keys
    are decamelized class names transformed to identifiers and with
    `presenter` suffix removed."""
    presenters = {}
    for c in subclass_iterator(Presenter):
        name = to_identifier(decamelize(c.__name__))
        if name.endswith("_presenter"):
            name = name[:-10]
        presenters[name] = c

    return presenters

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

