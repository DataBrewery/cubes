from .errors import *
from StringIO import StringIO

try:
    import jinja2
except ImportError:
    from .common import MissingPackage
    jinja2 = MissingPackage("jinja2", "Templating engine")

__all__ = [
            "create_presenter",
            "register_presenter",
            "TextTablePresenter"
            ]

_presenters = {
        }

def register_presenter(presenter_type, factory):
    """Register presenter factory with type name `presenter_type`"""

    _presenters[presenter_type] = factory

def create_presenter(presenter_type, *args, **kwargs):
    """Create a presenter of type `presenter_type`"""

    try:
        presenter_factory = _presenters[type]
    except KeyError:
        # FIXME: camelize
        #
        presenter_factory = None

    if not presenter_factory:
        raise CubesError("unknown presenter '%s'" % presenter_type)

    return presenter_factory(*args, **kwargs)

def _jinja_env():
    """Create and return cubes jinja2 environment"""
    loader = jinja2.PackageLoader('cubes', 'templates')
    env = jinja2.Environment(loader=loader)
    return env

class TextTablePresenter(object):
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


#class SimpleHtmlTablePresenter(object):
#    def __init__(self):
#        """Create a simple HTML table presenter"""
#
#        super(SimpleTablePresenter, self).__init__()
#        self.env = _jinja_env()
#        self.template = self.env.get_template("simple_table.html")
#
#    def present(result, dimension, measures):
#        hierarchy = dimension.hierarchy()
#        cut = result.cell.cut_for_dimension(dimension)
#
#        if cut:
#            path = cut.path
#        else:
#            path = []
#
#        levels = hierarchy.levels_for_path(path)
#        if levels:
#            next_level = hierarchy.next_level(levels[-1])
#        else:
#            next_level = hierarchy.next_level(None)
#
#        is_last = hierarchy.is_last(next_level)
#
#        output = self.template.render(dimension=dimension,
#                                      next_level=next_level,
#                                      result=result,
#                                      is_last=is_last)
#        return output
#
