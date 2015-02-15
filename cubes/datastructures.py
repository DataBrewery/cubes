# -*- coding=utf -*-
"""
    cubes.datastructures
    ~~~~~~~~~~~~~~~~~~~~~

    Utility data structures.
"""


from collections import MutableMapping
import sys


__all__ = [
    "AttributeGetter",
    "AttributeDictMixin",
    "AttributeDict",
    "DictAttribute",
    "FlatAccessDict",
]


# Helper class for Python attribute getter
class AttributeGetter(object):
    def __init__(self, getter):
        self.getter = getter

    def __getattr__(self, name):
        return self.getter(name)

#
# Credits:
# Originally from the Celery project:  http://www.celeryproject.org
#
class AttributeDictMixin(object):
    """Augment classes with a Mapping interface by adding attribute access.

    I.e. `d.key -> d[key]`.

    """

    def __getattr__(self, k):
        """`d.key -> d[key]`"""
        try:
            return self[k]
        except KeyError:
            raise AttributeError(
                '{0!r} object has no attribute {1!r}'.format(
                    type(self).__name__, k))

    def __setattr__(self, key, value):
        """`d[key] = value -> d.key = value`"""
        self[key] = value


class AttributeDict(dict, AttributeDictMixin):
    """Dict subclass with attribute access."""
    pass


class DictAttribute(object):
    """Dict interface to attributes.

    `obj[k] -> obj.k`
    `obj[k] = val -> obj.k = val`

    """
    obj = None

    def __init__(self, obj):
        object.__setattr__(self, 'obj', obj)

    def __getattr__(self, key):
        return getattr(self.obj, key)

    def __setattr__(self, key, value):
        return setattr(self.obj, key, value)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, default):
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return default

    def __getitem__(self, key):
        try:
            return getattr(self.obj, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        setattr(self.obj, key, value)

    def __contains__(self, key):
        return hasattr(self.obj, key)

    def _iterate_keys(self):
        return iter(dir(self.obj))
    iterkeys = _iterate_keys

    def __iter__(self):
        return self._iterate_keys()

    def _iterate_items(self):
        for key in self._iterate_keys():
            yield key, getattr(self.obj, key)
    iteritems = _iterate_items

    def _iterate_values(self):
        for key in self._iterate_keys():
            yield getattr(self.obj, key)
    itervalues = _iterate_values

    if sys.version_info[0] == 3:  # pragma: no cover
        items = _iterate_items
        keys = _iterate_keys
        values = _iterate_values
    else:

        def keys(self):
            return list(self)

        def items(self):
            return list(self._iterate_items())

        def values(self):
            return list(self._iterate_values())

MutableMapping.register(DictAttribute)

class FlatAccessDict(dict):
    """A dictionary where items can be accessed by a 'dotted' path. For
    example `d["foo.bar"]` will be the same as `d["foo"]["bar"]`"""

    def __getitem__(self, key):
        path = key.split(".")
        obj = super(FlatAccessDict, self).__getitem__(path[0])

        for item in path[1:]:
            obj = obj[item]

        return obj

    def __contains__(self, key):
        path = key.split(".")

        if not super(FlatAccessDict, self).__contains__(path[0]):
            return False

        obj = self[path[0]]

        for item in path[1:]:
            if not item in obj:
                return False
            obj = obj[item]

        return True

    def pop(self, key, default=None):
        path = key.split(".")
        owner = self

        # TODO: should we `del` when owner of popped object is empty?

        for item in path[:-1]:
            owner = owner[item]

        if owner is self:
            return super(FlatAccessDict, self).pop(key, default)
        else:
            return owner.pop(path[-1], default)

