"""Exceptions used in Cubes.

The base exception calss is :class:`.CubesError`."""

class CubesError(Exception):
    """Generic error class."""

class ModelError(CubesError):
    """Model related exception."""
    
class ModelInconsistencyError(ModelError):
    """Raised when there is incosistency in model structure."""

class NoSuchDimensionError(ModelError):
    """Raised when an unknown dimension is requested."""

class NoSuchAttributeError(ModelError):
    """Raised when an unknown attribute, measure or detail requested."""
    
class ArgumentError(CubesError):
    """Raised when an invalid or conflicting function argument is supplied.
    """

class MappingError(CubesError):
    """Raised when there are issues by mapping from logical model to physical
    database schema. """

class BrowserError(CubesError):
    """AggregationBrowser related exception."""
    pass
