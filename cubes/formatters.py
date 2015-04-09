# -*- coding: utf-8 -*-

from __future__ import print_function

from collections import namedtuple
from .common import SlicerJSONEncoder

from .errors import ArgumentError
from .compat import StringIO, to_str
from . import ext

from .browser import SPLIT_DIMENSION_NAME
from .common import CSVGenerator

try:
    import jinja2
except ImportError:
    from .common import MissingPackage
    jinja2 = MissingPackage("jinja2", "Templating engine")


__all__ = [
            "create_formatter",
            "CrossTableFormatter",
            "HTMLCrossTableFormatter",
            ]

def create_formatter(type_, *args, **kwargs):
    """Creates a formatter of type `type`. Passes rest of the arguments to the
    formatters initialization method."""
    return ext.formatter(type_, *args, **kwargs)


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
    def __call__(self, *args, **kwargs):
        return self.format(*args, **kwargs)


# Main pre-formatting
#

CrossTable = namedtuple("CrossTable", ["columns", "rows", "data"])

def make_cross_table(result, onrows=None, oncolumns=None, aggregates=None,
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

    cube = result.cell.cube
    aggregates = cube.get_aggregates(aggregates)

    matrix = {}
    row_hdrs = []
    column_hdrs = []

    labels = [agg.label for agg in aggregates]
    agg_refs = [agg.ref for agg in aggregates]

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

                matrix[(hrow, hcol)] = record[agg.ref]

    data = []

    for hrow in row_hdrs:
        row = [matrix.get((hrow, hcol)) for hcol in column_hdrs]
        data.append(row)

    return CrossTable(column_hdrs, row_hdrs, data)


def coalesce_table_labels(attributes, onrows, oncolumns):
    """Returns a tuple 9`onrows`, `oncolumns`) containing `attributes`. If
    both are empty, all attributes will be put on rows. If one of the two is
    empty, the rest of attributes is put on that axis."""
    if not onrows or not oncolumns:
        onrows = onrows or []
        oncolumns = oncolumns or []

        if not onrows:
            onrows = [attr for attr in attributes if attr not in oncolumns]

        if not oncolumns:
            oncolumns = [attr for attr in attributes if attr not in onrows]

    return(onrows, oncolumns)


class CrossTableFormatter(Formatter):
    __options__ = [
                {
                    "name": "indent",
                    "type": "integer",
                    "label": "Output indent"
                },
            ]

    mime_type = "application/json"

    def __init__(self, indent=None):
        """Creates a cross-table formatter for JSON output.

        Arguments:

        * `indent` – output indentation

        If aggregates are put on rows or columns, then respective row or
        column is added per aggregate. The data contains single aggregate
        values.

        If aggregates are put in the table as cells, then the data contains
        tuples of aggregates in the order as specified in the `aggregates`
        argument of `format()` method.
        """

        self.indent = indent or 4
        self.encoder = SlicerJSONEncoder(indent=indent)

    def format(self, cube, result, onrows=None, oncolumns=None, aggregates=None,
               aggregates_on=None):

        onrows, oncolumns = coalesce_table_labels(result.attributes,
                                                  onrows,
                                                  oncolumns)
        table = make_cross_table(result,
                                 onrows=onrows,
                                 oncolumns=oncolumns,
                                 aggregates=aggregates,
                                 aggregates_on=aggregates_on)

        d = {
            "columns": table.columns,
            "rows": table.rows,
            "data": table.data
        }
        output = self.encoder.encode(d)

        return output


class HTMLCrossTableFormatter(CrossTableFormatter):
    __options__ = [
                {
                    "name": "table_style",
                    "description": "CSS style for the table"
                }
            ]
    mime_type = "text/html"

    def __init__(self, table_style=None):
        """Create a simple HTML table formatter. See `CrossTableFormatter` for
        information about arguments."""

        self.env = _jinja_env()
        self.template = self.env.get_template("cross_table.html")
        self.table_style = table_style

    def format(self, cube, result, onrows=None, oncolumns=None, aggregates=None,
                aggregates_on=None):

        onrows, oncolumns = coalesce_table_labels(result.attributes,
                                                  onrows,
                                                  oncolumns)
        table = make_cross_table(result,
                                 onrows=onrows,
                                 oncolumns=oncolumns,
                                 aggregates=aggregates,
                                 aggregates_on=aggregates_on)

        output = self.template.render(table=table,
                                      table_style=self.table_style)
        return output

class CSVFormatter(Formatter):
    def format(self, cube, result, onrows=None, oncolumns=None, aggregates=None,
               aggregates_on=None):

        if any([onrows, oncolumns]):
            raise ArgumentError("Column/row layout options are not supported")

        header = []
        for l in result.labels:
            # TODO: add a little bit of polish to this
            if l == SPLIT_DIMENSION_NAME:
                header.append('Matches Filters')
            else:
                header += [attr.label or attr.name
                           for attr in cube.get_attributes([l], aggregated=True)]

        fields = result.labels
        generator = CSVGenerator(result,
                                 fields,
                                 include_header=bool(header),
                                 header=header)
        # TODO: this is Py3 hack over Py2 hack
        rows = [to_str(row) for row in generator.csvrows()]
        output = "".join(rows)
        return output
