# -*- coding: utf-8 -*-
"""Exceptions used in Cubes.

The base exception calss is :class:`.CubesError`."""

from collections import OrderedDict

class CubesError(Exception):
    """Generic error class."""

class InconsistencyError(CubesError):
    """Raised when something bad happened in cubes – very likely an edge
    case that is not handled properly.

    It is very unlikely that the user might fix this error by changing his/her
    input.
    """

class UserError(CubesError):
    """Superclass for all errors caused by the cubes and slicer users. Error
    messages from this error might be safely passed to the front-end. Do not
    include any information that you would not like to be public.

    Users can fix the error."""
    error_type = "unknown_user_error"

class InternalError(CubesError):
    """Superclass for all errors that happened on the server side:
    configuration issues, connection problems, model inconsistencies...

    If you handle this exception, don't display content of this error to the
    clients (such as over the web), as it might contain information about the
    server configuration, database or other internals.
    """
    error_type = "internal_error"

class ConfigurationError(InternalError):
    """Raised when there is a problem with workspace configuration assumed."""

class BackendError(InternalError):
    """Raised by a backend. Should be handled separately, for example: should
    not be passed to the client from the server due to possible internal
    schema exposure.
    """

class WorkspaceError(InternalError):
    """Backend Workspace related exception."""

class BrowserError(InternalError):
    """AggregationBrowser related exception."""
    pass

class StoreError(InternalError):
    """AggregationBrowser related exception."""
    pass

class ModelError(InternalError):
    """Model related exception."""

class ExpressionError(ModelError):
    """Expression related exception such as unknown attribute or cirular
    attribute reference"""

# TODO: necessary? or rename to PhysicalModelError
class MappingError(ModelError):
    """Raised when there are issues by mapping from logical model to physical
    database schema. """


# TODO: change all instances to ModelError
class ModelInconsistencyError(ModelError):
    """Raised when there is incosistency in model structure."""

class MissingObjectError(UserError):
    error_type = "missing_object"
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
    object_type = "dimension"

class NoSuchCubeError(MissingObjectError):
    """Raised when an unknown cube is requested."""
    object_type = "cube"

class NoSuchAttributeError(UserError):
    """Raised when an unknown attribute, measure or detail requested."""
    object_type = "attribute"

class ArgumentError(UserError):
    """Raised when an invalid or conflicting function argument is supplied.
    """

class HierarchyError(UserError):
    """Raised when attemt to get level deeper than deepest level in a
    hierarchy"""
    error_type = "hierarchy"


# Helper exceptions
# =================
#
# Not quite errors, but used for signalling
#
class TemplateRequired(ModelError):
    """Raised by a model provider which can provide a dimension, but requires
    a template. Signals to the caller that the creation of a dimension should
    be retried when the template is available."""

    def __init__(self, template):
        self.template = template
    def __str__(self):
        return self.template

