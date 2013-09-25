"""Exceptions used in Cubes.

The base exception calss is :class:`.CubesError`."""

class ConfigurationError(Exception):
    """Raised when there is a problem with workspace configuration assumed."""

class CubesError(Exception):
    """Generic error class."""

class ModelError(CubesError):
    """Model related exception."""

class ModelInconsistencyError(ModelError):
    """Raised when there is incosistency in model structure."""

class MissingObjectError(ModelError):
    def __init__(self, name, reason=None):
        self.name = name
        self.reason = reason

    def __str__(self):
        return self.name

class NoSuchDimensionError(MissingObjectError):
    """Raised when an unknown dimension is requested."""

class NoSuchCubeError(MissingObjectError):
    """Raised when an unknown cube is requested."""

class TemplateRequired(ModelError):
    """Raised by a model provider which can provide a dimension, but requires
    a template. Signals to the caller that the creation of a dimension should
    be retried when the template is available."""

    def __init__(self, template):
        self.template = template
    def __str__(self):
        return self.template

class NoSuchAttributeError(ModelError):
    """Raised when an unknown attribute, measure or detail requested."""

class ArgumentError(CubesError):
    """Raised when an invalid or conflicting function argument is supplied.
    """

class BackendError(CubesError):
    """Raised by a backend. Should be handled separately, for example: should
    not be passed to the client from the server due to possible internal
    schema exposure.
    """

class MappingError(BackendError):
    """Raised when there are issues by mapping from logical model to physical
    database schema. """

class WorkspaceError(CubesError):
    """Backend Workspace related exception."""

class BrowserError(CubesError):
    """AggregationBrowser related exception."""
    pass

class HierarchyError(CubesError):
    """Raised when attemt to get level deeper than deepest level in a
    hierarchy"""
