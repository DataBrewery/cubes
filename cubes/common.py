# -*- coding=utf -*-
"""Utility functions for computing combinations of dimensions and hierarchy
levels"""

import itertools
import logging
import sys
import re
import collections

__all__ = [
    "logger_name",
    "get_logger",
    "create_logger",
    "IgnoringDictionary",
    "MissingPackage",
    "localize_common",
    "localize_attributes",
    "get_localizable_attributes",
    "decamelize",
    "to_identifier",
    "collect_subclasses"
]

logger_name = "cubes"
logger = None

def get_logger():
    """Get brewery default logger"""
    global logger

    if logger:
        return logger
    else:
        return create_logger()

def create_logger(level=None):
    """Create a default logger"""
    global logger
    logger = logging.getLogger(logger_name)

    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if level:
        level = level.lower()
        levels = {  "info": logging.INFO,
                    "debug": logging.DEBUG,
                    "warn":logging.WARN,
                    "error": logging.ERROR}
        if level not in levels:
            logger.warn("Unknown logging level '%s', keeping default" % level)
        else:
            logger.setLevel(levels[level])

    return logger

class IgnoringDictionary(dict):
    """Simple dictionary extension that will ignore any keys of which values
    are empty (None/False)"""
    def setnoempty(self, key, value):
        """Set value in a dictionary if value is not null"""
        if value:
            self[key] = value

class MissingPackageError(Exception):
    """Exception raised when encountered a missing package."""
    pass

class MissingPackage(object):
    """Bogus class to handle missing optional packages - packages that are not
    necessarily required for Cubes, but are needed for certain features."""

    def __init__(self, package, feature = None, source = None, comment = None):
        self.package = package
        self.feature = feature
        self.source = source
        self.comment = comment

    def __call__(self, *args, **kwargs):
        self._fail()

    def __getattr__(self, name):
        self._fail()

    def _fail(self):
        if self.feature:
            use = " to be able to use: %s" % self.feature
        else:
            use = ""

        if self.source:
            source = " from %s" % self.source
        else:
            source = ""

        if self.comment:
            comment = ". %s" % self.comment
        else:
            comment = ""

        raise MissingPackageError("Optional package '%s' is not installed. "
                                  "Please install the package%s%s%s" %
                                      (self.package, source, use, comment))


def expand_dictionary(record, separator = '.'):
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

def localize_common(obj, trans):
    """Localize common attributes: label and description"""

    if "label" in trans:
        obj.label = trans["label"]
    if "description" in trans:
        obj.description = trans["description"]

def localize_attributes(attribs, translations):
    """Localize list of attributes. `translations` should be a dictionary with
    keys as attribute names, values are dictionaries with localizable
    attribute metadata, such as ``label`` or ``description``."""

    for (name, atrans) in translations.items():
        attrib = attribs[name]
        localize_common(attrib, atrans)

def get_localizable_attributes(obj):
    """Returns a dictionary with localizable attributes of `obj`."""

    # FIXME: use some kind of class attribute to get list of localizable attributes

    locale = {}
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

def subclass_iterator(cls, _seen=None):
    """
    Generator over all subclasses of a given class, in depth first order.

    Source: http://code.activestate.com/recipes/576949-find-all-subclasses-of-a-given-class/
    """

    if not isinstance(cls, type):
        raise TypeError('_subclass_iterator must be called with '
                        'new-style classes, not %.100r' % cls)

    _seen = _seen or set()

    try:
        subs = cls.__subclasses__()
    except TypeError: # fails only when cls is type
        subs = cls.__subclasses__(cls)
    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for sub in subclass_iterator(sub, _seen):
                yield sub

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

def collect_subclasses(parent, suffix=None):
    """Collect all subclasses of `parent` and return a dictionary where keys
    are decamelized class names transformed to identifiers and with
    `suffix` removed."""
    subclasses = {}
    for c in subclass_iterator(parent):
        name = to_identifier(decamelize(c.__name__))
        if suffix and name.endswith(suffix):
            name = name[:-len(suffix)]
        subclasses[name] = c

    return subclasses

def string_to_value(astring, value_type, label=None):
    """Convert string into an object value of `value_type`. The type might be:
        `string` (no conversion), `integer`, `float`, `list` – comma separated
        list of strings.
    """
    value_type = value_type.lower()

    try:
        if value_type == 'string':
            return_value = astring
        elif value_type == 'list':
            return_value = astring.split(",")
        elif value_type == "float":
            return_value = float(astring)
        elif value_type == "integer":
            return_value = int(astring)
        elif value_type == "bool":
            return_value = astring.lower() in ["true", "yes", "1"]
    except ValueError:
        if label:
            label = "parameter %s " % label
        else:
            label = ""

        raise ArgumentError("Unable to convert %svalue '%s' into type %s" %
                                                (label, astring, value_type))
    return return_value
