# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from collections import OrderedDict


class CubesError(Exception):
    pass


class ModelError(CubesError):
    error_type = 'model_error'


class MissingObjectError(CubesError):
    error_type = 'missing_object'
    object_type = None

    def __init__(self, message=None, name=None):
        self.message = message
        self.name = name

    def __str__(self):
        return self.message or self.name

    def to_dict(self):
        d = OrderedDict()
        d["object"] = self.name
        d["message"] = self.message
        if self.object_type:
            d["object_type"] = self.object_type

        return d


class NoSuchDimensionError(MissingObjectError):
    """Raised when an unknown dimension is requested."""
    object_type = 'dimension'


class NoSuchAttributeError(MissingObjectError):
    """Raised when an unknown attribute, measure or detail requested."""
    object_type = 'attribute'


class ArgumentError(CubesError):
    """Raised when an invalid or conflicting function argument is supplied.
    """
