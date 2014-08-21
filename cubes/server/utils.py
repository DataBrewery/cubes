# -*- encoding: utf-8 -*-

from __future__ import absolute_import

from flask import Request, Response, request, g
from datetime import datetime

import datetime
import decimal
import codecs
import json
import csv

from .errors import *
from .. import compat


def str_to_bool(string):
    """Convert a `string` to bool value. Returns ``True`` if `string` is
    one of ``["true", "yes", "1", "on"]``, returns ``False`` if `string` is
    one of  ``["false", "no", "0", "off"]``, otherwise returns ``None``."""

    if string is not None:
        if string.lower() in ["true", "yes", "1", "on"]:
            return True
        elif string.lower() in["false", "no", "0", "off"]:
            return False

    return None


def validated_parameter(args, name, values=None, default=None,
                        case_sensitive=False):
    """Return validated parameter `param` that has to be from the list of
    `values` if provided."""

    param = args.get(name)
    if param:
        param = param.lower()
    else:
        param = default

    if not values:
        return param
    else:
        if values and param not in values:
            list_str = ", ".join(values)
            raise RequestError("Parameter '%s' should be one of: %s"
                            % (name, list_str) )
        return param


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
        if type(o) == decimal.Decimal:
            return float(o)
        if type(o) == datetime.date or type(o) == datetime.datetime:
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


class CSVGenerator(object):
    def __init__(self, records, fields, include_header=True,
                header=None, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.records = records

        self.include_header = include_header
        self.header = header

        self.fields = fields
        self.queue = compat.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.encoder = codecs.getincrementalencoder(encoding)()

    def csvrows(self):
        if self.include_header:
            yield self._row_string(self.header or self.fields)

        for record in self.records:
            row = []
            for field in self.fields:
                value = record.get(field)
                if isinstance(value, compat.string_type):
                    row.append(value.encode("utf-8"))
                elif value is not None:
                    row.append(compat.text_type(value))
                else:
                    row.append(None)

            yield self._row_string(row)

    def _row_string(self, row):
        self.writer.writerow(row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # empty queue
        self.queue.truncate(0)

        return data


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
            yield "%s%s" % (string, self.separator)

class UnicodeCSVWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.

    From: <http://docs.python.org/lib/csv-examples.html>
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        new_row = []
        for value in row:
            if isinstance(value, compat.string_type):
                new_row.append(value.encode("utf-8"))
            elif value:
                new_row.append(compat.text_type(value))
            else:
                new_row.append(None)

        self.writer.writerow(new_row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

class CustomDict(dict):
    def __getattr__(self, attr):
        try:
            return super(CustomDict, self).__getitem__(attr)
        except KeyError:
            return super(CustomDict, self).__getattribute__(attr)

    def __setattr__(self, attr, value):
        self.__setitem__(attr,value)


# Utils
# =====

def jsonify(obj):
    """Returns a ``application/json`` `Response` object with `obj` converted
    to JSON."""

    if g.prettyprint:
        indent = 4
    else:
        indent = None

    encoder = SlicerJSONEncoder(indent=indent)
    encoder.iterator_limit = g.json_record_limit
    data = encoder.iterencode(obj)

    return Response(data, mimetype='application/json')


def formated_response(response, fields, labels, iterable=None):
    """Wraps request which returns response that can be formatted. The
    `data_attribute` is name of data attribute or key in the response that
    contains formateable data."""

    output_format = validated_parameter(request.args, "format",
                                        values=["json", "json_lines", "csv"],
                                        default="json")

    header_type = validated_parameter(request.args, "header",
                                      values=["names", "labels", "none"],
                                      default="labels")

    # Construct the header
    if header_type == "names":
        header = fields
    elif header_type == "labels":
        header = labels
    else:
        header = None


    # If no iterable is provided, we assume the response to be iterable
    iterable = iterable or response

    if output_format == "json":
        return jsonify(response)
    elif output_format == "json_lines":
        return Response(JSONLinesGenerator(iterable),
                        mimetype='application/x-json-lines')
    elif output_format == "csv":
        generator = CSVGenerator(iterable,
                                 fields,
                                 include_header=bool(header),
                                 header=header)

        headers = {"Content-Disposition": 'attachment; filename="facts.csv"'}

        return Response(generator.csvrows(),
                        mimetype='text/csv',
                        headers=headers)

def read_server_config(config):
    if not config:
        return compat.configparser.SafeConfigParser()
    elif isinstance(config, compat.string_type):
        try:
            path = config
            config = compat.configparser.SafeConfigParser()
            config.read(path)
        except Exception as e:
            raise Exception("Unable to load configuration: %s" % e)
    return config

