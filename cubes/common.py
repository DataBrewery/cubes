# -*- encoding: utf-8 -*-

"""Utility functions for computing combinations of dimensions and hierarchy
levels"""

from typing import (
    Any,
    Collection,
    Dict,
    Hashable,
    List,
    Optional,
    TypeVar,
    Union,
)

import re
import os.path
import json

from collections import OrderedDict

from .types import JSONType
from .errors import ModelInconsistencyError, ArgumentError, ConfigurationError

__all__ = [
    "IgnoringDictionary",
    "MissingPackage",
    "localize_common",
    "localize_attributes",
    "get_localizable_attributes",
    "decamelize",
    "to_identifier",
    "assert_instance",
    "assert_all_instances",
    "read_json_file",
    "sorted_dependencies",
    "to_str",
    "JSONType",
]


def to_str(b: bytes) -> str:
    """Convert UTF-8 binary `b` into string."""
    return b.decode("utf-8")


class IgnoringDictionary(OrderedDict):
    """Simple dictionary extension that will ignore any keys of which values
    are empty (None/False)"""
    def __setitem__(self, key: str, value: Any) -> None:
        if value is not None:
            super(IgnoringDictionary, self).__setitem__(key, value)

    def set(self, key: str, value: Any) -> None:
        """Sets `value` for `key` even if value is null."""
        super(IgnoringDictionary, self).__setitem__(key, value)

    def __repr__(self) -> str:
        items = []
        for key, value in self.items():
            item = '%s: %s' % (repr(key), repr(value))
            items.append(item)

        return "{%s}" % ", ".join(items)


def assert_instance(obj: Any, class_: Any, label: str) -> None:
    """Raises ArgumentError when `obj` is not instance of `cls`"""
    if not isinstance(obj, class_):
        raise ModelInconsistencyError("%s should be sublcass of %s, "
                                      "provided: %s" % (label,
                                                        class_.__name__,
                                                        type(obj).__name__))


def assert_all_instances(list_: List[Any], class_: Any,
                         label: str="object") -> None:
    """Raises ArgumentError when objects in `list_` are not instances of
    `cls`"""
    for obj in list_ or []:
        assert_instance(obj, class_, label="object")


class MissingPackageError(Exception):
    """Exception raised when encountered a missing package."""
    pass


class MissingPackage:
    """Bogus class to handle missing optional packages - packages that are not
    necessarily required for Cubes, but are needed for certain features."""

    package: str
    feature: Optional[str]
    source: Optional[str]
    comment: Optional[str]

    def __init__(self,
            package: str,
            feature:Optional[str]=None,
            source:Optional[str]=None,
            comment:Optional[str]=None) -> None:
        self.package = package
        self.feature = feature
        self.source = source
        self.comment = comment

    def __call__(self, *args: Any, **kwargs: Any) -> None:
        self._fail()

    def __getattr__(self, name: str) -> None:
        self._fail()

    def _fail(self) -> None:
        if self.feature:
            use = f" to be able to use: {self.feature}"
        else:
            use = ""

        if self.source:
            source = f" from {self.source}"
        else:
            source = ""

        if self.comment:
            comment = f". {self.comment}"
        else:
            comment = ""

        raise MissingPackageError(f"Optional package '{self.package}' "
                                  f"is not installed. "
                                  f"Please install the package"
                                  f"{source}{use}{comment}")

# ...

def optional_import(name: str,
                    feature:Optional[str]=None,
                    source:Optional[str]=None,
                    comment:Optional[str]=None) -> MissingPackage:
    """Optionally import package `name`. If package does not exist, import a
    placeholder object, that raises an exception with more detailed
    description about the missing package."""

    try:
        return __import__(name)
    except ImportError:
        return MissingPackage(name, feature, source, comment)


def expand_dictionary(record: Dict[str, Any],
                      separator:str='.') -> Dict[str,Any]:
    """Return expanded dictionary: treat keys are paths separated by
    `separator`, create sub-dictionaries as necessary"""

    result: Dict[str, Any] = {}

    for key, value in record.items():
        current = result
        path = key.split(separator)
        for part in path[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[path[-1]] = value
    return result


# TODO: py3: Typecheck `obj` with some protocol
# TODO: Make this a pure function
def localize_common(obj: Any, trans: JSONType) -> None:
    """Localize common attributes: label and description"""

    if "label" in trans:
        obj.label = trans["label"]
    if "description" in trans:
        obj.description = trans["description"]


# TODO: Make this a pure function
def localize_attributes(attribs: Dict[str, Any],
                        translations:Dict[str, JSONType]) -> None:
    """Localize list of attributes. `translations` should be a dictionary with
    keys as attribute names, values are dictionaries with localizable
    attribute metadata, such as ``label`` or ``description``."""

    for (name, atrans) in translations.items():
        attrib = attribs[name]
        localize_common(attrib, atrans)


def get_localizable_attributes(obj: Any) -> Dict[str, str]:
    """Returns a dictionary with localizable attributes of `obj`."""

    # FIXME: use some kind of class attribute to get list of localizable attributes

    locale: Dict[str, str] = {}
    try:
        if obj.label:
            locale["label"] = obj.label
    except:
        pass

    try:
        if obj.description:
            locale["description"] = obj.description
    except:
        pass

    return locale


def decamelize(name: str) -> str:
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)


def to_identifier(name: str) -> str:
    return re.sub(r' ', r'_', name).lower()


def to_label(name: str, capitalize: bool=True) -> str:
    """Converts `name` into label by replacing underscores by spaces. If
    `capitalize` is ``True`` (default) then the first letter of the label is
    capitalized."""

    label = name.replace("_", " ")
    if capitalize:
        label = label.capitalize()

    return label


# FIXME: type: Fix the type
def coalesce_option_value(value: Any, value_type: str, label: str=None) -> Any:
    """Convert string into an object value of `value_type`. The type might be:
        `string` (no conversion), `integer`, `float`, `list` – comma separated
        list of strings.
    """
    return_value: Union[str, List[str], float, int, bool]
    value_type = value_type.lower()

    try:
        if value_type in ('string', 'str'):
            return_value = str(value)
        elif value_type == 'list':
            if isinstance(value, str):
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
            elif isinstance(value, str):
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

        raise ArgumentError(f"Unable to convert {label}value '{value}' "
                            f"into type {value_type}")
    return return_value


# FIXME: type: Fix the types
def coalesce_options(options: Any, types: Any) -> Any:
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


def read_json_file(path:str, kind:str=None) -> JSONType:
    """Read a JSON from `path`. This is convenience function that provides
    more descriptive exception handling."""

    kind = "%s " % str(kind) if kind else ""

    if not os.path.exists(path):
         raise ConfigurationError("Can not find %sfile '%s'"
                                 % (kind, path))

    try:
        f = open(path, encoding="utf-8")
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


# FIXME: type: fix the type
def sorted_dependencies(graph: Any) -> Any:
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

def list_hash(values: Collection[Hashable]) -> int:
    """Return a hash value of a sequence of hashable items."""
    hash_value = 0
    
    for value in values:
        hash_value = hash_value ^ hash(value)

    return hash_value
