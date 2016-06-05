# -*- coding: utf-8 -*-

from __future__ import print_function

import json
import csv
import codecs
import decimal
import datetime

from collections import namedtuple

try:
    import jinja2
except ImportError:
    from .common import MissingPackage
    jinja2 = MissingPackage("jinja2", "Templating engine")

from .errors import ArgumentError
from . import compat
from . import ext

from .browser import SPLIT_DIMENSION_NAME


__all__ = [
    "create_formatter",
    "CrossTableFormatter",
    "HTMLCrossTableFormatter",
    "SlicerJSONEncoder",
    "csv_generator",
    "JSONLinesGenerator",
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


def csv_generator_p2(records, fields, include_header=True, header=None,
                     dialect=csv.excel):

    def _row_string(row):
        writer.writerow(row)
        # Fetch UTF-8 output from the queue ...
        data = queue.getvalue()
        data = compat.to_unicode(data)
        # ... and reencode it into the target encoding
        data = encoder.encode(data)
        # empty queue
        queue.truncate(0)

        return data

    queue = compat.StringIO()
    writer = csv.writer(queue, dialect=dialect)
    encoder = codecs.getincrementalencoder("utf-8")()

    if include_header:
        yield _row_string(header or fields)

    for record in records:
        row = []
        for field in fields:
            value = record.get(field)
            if isinstance(value, compat.string_type):
                row.append(value.encode("utf-8"))
            elif value is not None:
                row.append(compat.text_type(value))
            else:
                row.append(None)

        yield _row_string(row)


def csv_generator_p3(records, fields, include_header=True, header=None,
                     dialect=csv.excel):

    def _row_string(row):
        writer.writerow(row)
        data = queue.getvalue()
        queue.truncate(0)

        return data

    queue = compat.StringIO()
    writer = csv.writer(queue, dialect=dialect)

    if include_header:
        yield _row_string(header or fields)

    for record in records:
        row = [record.get(field) for field in fields]

        yield _row_string(row)


if compat.py3k:
    csv_generator = csv_generator_p3
else:
    csv_generator = csv_generator_p2


class JSONLinesGenerator(object):
    def __init__(self, iterable, separator='\n'):
        """Creates a generator that yields one JSON record per record from
        `iterable` separated by a newline character.."""
        self.iterable = iterable
        self.separator = separator

        self.encoder = SlicerJSONEncoder(indent=None)

    def __iter__(self):
        for obj in self.iterable:
            string = self.encoder.encode(obj)
            yield u"{}{}".format(string, self.separator)


class SlicerJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        """Creates a JSON encoder that will convert some data values and also allows
        iterables to be used in the object graph.

        :Attributes:
        * `iterator_limit` - limits number of objects to be fetched from
          iterator. Default: 1000.
        """

        super(SlicerJSONEncoder, self).__init__(*args, **kwargs)

        self.iterator_limit = 1000

    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if hasattr(o, "to_dict") and callable(getattr(o, "to_dict")):
            return o.to_dict()
        else:
            array = None
            try:
                # If it is an iterator, then try to construct array and limit number of objects
                iterator = iter(o)
                count = self.iterator_limit
                array = []
                for i, obj in enumerate(iterator):
                    array.append(obj)
                    if i >= count:
                        break
            except TypeError as e:
                # not iterable
                pass

            if array is not None:
                return array
            else:
                return json.JSONEncoder.default(self, o)


class Formatter(object):
    """Empty class for the time being. Currently used only for finding all
    built-in subclasses"""
    def __call__(self, *args, **kwargs):
        return self.format(*args, **kwargs)

    def format(self, *args, **kwargs):
        raise NotImplementedError("Subclasses are expected to implement "
                                  "the format() method")


# Main pre-formatting
#

CrossTable = namedtuple("CrossTable", ["columns", "rows", "data"])

def make_cross_table(result, onrows=None, oncolumns=None, aggregates_on=None):
    """
    Creates a cross table from a drilldown (might be any list of records).
    `onrows` contains list of attribute names to be placed at rows and
    `oncolumns` contains list of attribute names to be placet at columns.
    `aggregates_on` specifies where the aggregates will be incuded:

    * ``cells`` (default) – aggregates will be included in the data matrix
      cell
    * ``rows`` – there will be one row per aggregate per "on row" dimension
      member
    * ``columns`` – there will be one column per aggregate per "on column"
      dimension member

    Returns a named tuble with attributes:

    * `columns` - labels of columns. The tuples correspond to values of
      attributes in `oncolumns`.
    * `rows` - labels of rows as list of tuples. The tuples correspond to
      values of attributes in `onrows`.
    * `data` - list of aggregate data per row. Each row is a list of
      aggregate tuples.

    """

    if not result.drilldown:
        # TODO: we should at least create one-row/one-column table
        raise ArgumentError("Can't create cross-table without drilldown.")

    aggregates = result.aggregates

    matrix = {}
    row_hdrs = []
    column_hdrs = []

    agg_refs = [agg.ref for agg in aggregates]

    if aggregates_on is None or aggregates_on == "cells":
        for record in result.cells:
            # Get table coordinates
            hrow = tuple(record[f] for f in onrows)
            hcol = tuple(record[f] for f in oncolumns)

            if hrow not in row_hdrs:
                row_hdrs.append(hrow)
            if hcol not in column_hdrs:
                column_hdrs.append(hcol)

            matrix[(hrow, hcol)] = tuple(record[a] for a in agg_refs)

    else:
        for record in result.cells:
            # Get table coordinates
            base_hrow = [record[f] for f in onrows]
            base_hcol = [record[f] for f in oncolumns]

            for agg in aggregates:

                if aggregates_on == "rows":
                    hrow = tuple(base_hrow + [agg.label or agg.name])
                    hcol = tuple(base_hcol)

                elif aggregates_on == "columns":
                    hrow = tuple(base_hrow)
                    hcol = tuple(base_hcol + [agg.label or agg.name])

                if hrow not in row_hdrs:
                    row_hdrs.append(hrow)

                if hcol not in column_hdrs:
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
        generator = csv_generator(result,
                                  fields,
                                  include_header=bool(header),
                                  header=header)
        # TODO: this is Py3 hack over Py2 hack
        rows = [compat.to_str(row) for row in generator]
        output = "".join(rows)
        return output

