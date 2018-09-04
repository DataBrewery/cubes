# -*- encoding: utf-8 -*-

"""Utility functions for computing combinations of dimensions and hierarchy
levels"""

from __future__ import absolute_import

import inspect
import json
import os.path
import re
from collections import OrderedDict

from . import compat
from .errors import ArgumentError, ConfigurationError

__all__ = (
    "IgnoringDictionary",
    "decamelize",
    "to_identifier",
    'to_label',
    "read_json_file",
    "sorted_dependencies",
)


class IgnoringDictionary(OrderedDict):
    """Simple dictionary extension that will ignore any keys of which values
    are None"""

    def __setitem__(self, key, value):
        if value is not None:
            super(IgnoringDictionary, self).__setitem__(key, value)

    def set(self, key, value):
        """Sets `value` for `key` even if value is null."""
        super(IgnoringDictionary, self).__setitem__(key, value)

    def __repr__(self):
        items = []
        for key, value in self.items():
            item = '%s: %s' % (repr(key), repr(value))
            items.append(item)

        return '{%s}' % ', '.join(items)


def expand_dictionary(record, separator='.'):
    """Return expanded dictionary: treat keys are paths separated by
    `separator`, create sub-dictionaries as necessary"""

    result = {}
    for key, value in record.items():
        current = result
        path = key.split(separator)
        for part in path[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[path[-1]] = value
    return result


def decamelize(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)


def to_identifier(name):
    return re.sub(r' ', r'_', name).lower()


def to_label(name, capitalize=True):
    """Converts `name` into label by replacing underscores by spaces. If
    `capitalize` is ``True`` (default) then the first letter of the label is
    capitalized."""

    label = name.replace("_", " ")
    if capitalize:
        label = label.capitalize()

    return label


def coalesce_option_value(value, value_type, label=None):
    """Convert string into an object value of `value_type`. The type might be:
        `string` (no conversion), `integer`, `float`, `list` – comma separated
        list of strings.
    """
    value_type = value_type.lower()

    try:
        if value_type in ('string', 'str'):
            return_value = str(value)
        elif value_type == 'list':
            if isinstance(value, compat.string_type):
                return_value = value.split(",")
            else:
                return_value = list(value)
        elif value_type == "float":
            return_value = float(value)
        elif value_type in ["integer", "int"]:
            return_value = int(value)
        elif value_type in ["bool", "boolean"]:
            if not value:
                return_value = False
            elif isinstance(value, compat.string_type):
                return_value = value.lower() in ["1", "true", "yes", "on"]
            else:
                return_value = bool(value)
        else:
            raise ArgumentError("Unknown option value type %s" % value_type)

    except ValueError:
        if label:
            label = "parameter %s " % label
        else:
            label = ""

        raise ArgumentError("Unable to convert %svalue '%s' into type %s" %
                            (label, astring, value_type))
    return return_value


def coalesce_options(options, types):
    """Coalesce `options` dictionary according to types dictionary. Keys in
    `types` refer to keys in `options`, values of `types` are value types:
    string, list, float, integer or bool."""

    out = {}

    for key, value in options.items():
        if key in types:
            out[key] = coalesce_option_value(value, types[key], key)
        else:
            out[key] = value

    return out


def read_json_file(path, kind=None):
    """Read a JSON from `path`. This is convenience function that provides
    more descriptive exception handling."""

    kind = "%s " % str(kind) if kind else ""

    if not os.path.exists(path):
         raise ConfigurationError("Can not find %sfile '%s'"
                                 % (kind, path))

    try:
        f = compat.open_unicode(path)
    except IOError:
        raise ConfigurationError("Can not open %sfile '%s'"
                                 % (kind, path))

    try:
        content = json.load(f)
    except ValueError as e:
        raise SyntaxError("Syntax error in %sfile %s: %s"
                          % (kind, path, str(e)))
    finally:
        f.close()

    return content


def sorted_dependencies(graph):
    """Return keys from `deps` ordered by dependency (topological sort).
    `deps` is a dictionary where keys are strings and values are list of
    strings where keys is assumed to be dependant on values.

    Example::

        A ---> B -+--> C
                  |
                  +--> D --> E

    Will be: ``{"A": ["B"], "B": ["C", "D"], "D": ["E"],"E": []}``
    """

    graph = dict((key, set(value)) for key, value in graph.items())

    # L ← Empty list that will contain the sorted elements
    L = []

    # S ← Set of all nodes with no dependencies (incoming edges)
    S = set(parent for parent, req in graph.items() if not req)

    while S:
        # remove a node n from S
        n = S.pop()
        # insert n into L
        L.append(n)

        # for each node m with an edge e from n to m do
        #                         (n that depends on m)
        parents = [parent for parent, req in graph.items() if n in req]

        for parent in parents:
            graph[parent].remove(n)
            # remove edge e from the graph
            # if m has no other incoming edges then insert m into S
            if not graph[parent]:
                S.add(parent)

    # if graph has edges then -> error
    nonempty = [k for k, v in graph.items() if v]

    if nonempty:
        raise ArgumentError("Cyclic dependency of: %s"
                            % ", ".join(nonempty))
    return L


class AttrDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


class FactoryMixin(object):
    @classmethod
    def factory_key(cls, params):
        raise NotImplementedError(
            'Abstract method for "{}" class.'.format(cls.__name__)
        )

    @classmethod
    def registry(cls):
        raise NotImplementedError(
            'Abstract method for "{}" class.'.format(cls.__name__)
        )

    @classmethod
    def _get_init_arg_names(cls):
        arg_names = []
        init = cls.__dict__.get('__init__')
        if init:
            arg_names = inspect.getargspec(init).args
            arg_names = arg_names[1:]  # ignore "self"
        return arg_names

    @classmethod
    def build(cls, *args, **kws):
        arg_names = cls._get_init_arg_names()
        converted_kws = dict(zip(arg_names, args))
        converted_kws.update(kws)

        key = cls.factory_key(AttrDict(converted_kws))
        registry = cls.registry()

        cls_to_create = registry.get(key)
        if cls_to_create:
            return cls.on_building(cls_to_create, converted_kws)

        raise RuntimeError(
            'Unrecognized factory key "{}" for "{}" class.'
            .format(key, cls.__name__)
        )

    @classmethod
    def on_building(cls, cls_to_create, params):
        return cls_to_create(**params)
