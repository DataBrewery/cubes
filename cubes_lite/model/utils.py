# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from collections import OrderedDict
from operator import attrgetter

from cubes_lite.errors import ModelError, ArgumentError


def object_dict(objects, by_ref=False, error_message=None, error_dict=None, key_func=None):
    """Make an ordered dictionary from model objects `objects` where keys are
    object names. If `by_ref` is `True` then object's `ref` (reference) is
    used instead of object name. Keys are supposed to be unique in the list,
    otherwise an exception is raised."""

    objects = objects or []

    if by_ref:
        if key_func:
            raise ArgumentError(
                'Both `key_func` and `by_ref` arguments are disallowed'
            )
        key_func = attrgetter('ref')
    else:
        key_func = key_func or attrgetter('name')

    ordered = OrderedDict()

    items = ((key_func(obj), obj) for obj in objects)
    for key, value in items:
        if key in ordered:
            error_message = error_message or 'Duplicate key {key}'
            error_dict = error_dict or {}
            raise ModelError(error_message.format(key=key, **error_dict))
        ordered[key] = value

    return ordered


def assert_instance(obj, class_, label):
    """Raises ArgumentError when `obj` is not instance of `cls`"""

    if not isinstance(obj, class_):
        raise ModelError(
            '"{}" should be sublcass of "{}", provided: "{}"'
            .format(label, class_.__name__, type(obj).__name__)
        )


def assert_all_instances(list_, class_, label='object'):
    """Raises ArgumentError when objects in `list_` are not instances of
    `cls`"""

    for obj in list_ or []:
        assert_instance(obj, class_, label='object')


def ensure_list(model_data_list):
    if isinstance(model_data_list, dict):
        data = model_data_list.items()
        model_data_list = []
        for name, info in data:
            if isinstance(info, dict):
                item = dict(info, name=name)
            else:
                item = info
                item.name = name
            model_data_list.append(item)

    return model_data_list


class cached_property(object):
    """
    Decorator that converts a method with a single self argument into a
    property cached on the instance.

    Optional ``name`` argument allows you to make cached properties of other
    methods. (e.g.  url = cached_property(get_absolute_url, name='url') )
    """

    def __init__(self, func, name=None):
        self.func = func
        self.__doc__ = getattr(func, '__doc__')
        self.name = name or func.__name__

    def __get__(self, instance, cls=None):
        if instance is None:
            return self
        res = instance.__dict__[self.name] = self.func(instance)
        return res
