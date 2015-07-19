# -*- encoding: utf-8 -*-

from __future__ import absolute_import

from flask import Request, Response, request, g

import codecs
import json
import csv

from .errors import *
from ..formatters import csv_generator, JSONLinesGenerator, SlicerJSONEncoder
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


def formatted_response(response, fields, labels, iterable=None):
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
        generator = csv_generator(iterable,
                                 fields,
                                 include_header=bool(header),
                                 header=header)

        headers = {"Content-Disposition": 'attachment; filename="facts.csv"'}

        return Response(generator,
                        mimetype='text/csv',
                        headers=headers)


