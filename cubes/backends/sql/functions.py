
# -*- coding=utf -*-

from collections import namedtuple
from ...errors import *

try:
    import sqlalchemy
    import sqlalchemy.sql as sql
    from sqlalchemy.sql.functions import ReturnTypeFromArgs
except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")
    missing_error = MissingPackage("sqlalchemy", "SQL browser extensions")

    class ReturnTypeFromArgs(object):
        def __init__(*args, **kwargs):
            # Just fail by trying to call missing package
            missing_error()


__all__ = (
    "get_aggregate_function",
    "available_aggregate_functions"
)


class avg(ReturnTypeFromArgs):
    pass


# Works with PostgreSQL
class stddev(ReturnTypeFromArgs):
    pass


class variance(ReturnTypeFromArgs):
    pass


class AggregateFunction(object):
    requires_measure = True
    def __init__(self, name_, function_=None, *args, **kwargs):
        self.name = name_
        self.function = function_
        self.args = args
        self.kwargs = kwargs

    def __call__(self, aggregate, context):
        """Applied the function on the aggregate and returns labelled
        expression. SQL expression label is the aggregate's name. This method
        calls `apply()` method which can be overriden by subclasses."""

        expression = self.apply(aggregate, context)
        expression = expression.label(aggregate.name)
        return expression

    def apply(self, aggregate, context=None):
        """Apply the function on the aggregate. Subclasses might override this
        method and use other `aggregates` and browser context.

        Returns a SQLAlchemy expression."""

        if not context:
            raise InternalError("No context provided for AggregationFunction")

        if not aggregate.measure:
            raise ModelError("No measure specified for aggregate %s, "
                             "required for aggregate function %s"
                             % (str(aggregate), self.name))

        measure = context.cube.measure(aggregate.measure)
        expression = self.function(context.column(measure),
                                   *self.args,
                                   **self.kwargs)

        return expression

    def __str__(self):
        return self.name


class GenerativeFunction(AggregateFunction):
    def __init__(self, name, function=None, *args, **kwargs):
        """Creates a function that generates a value without using any of the
        measures."""
        super(GenerativeFunction, self).__init__(name, function)

    def apply(self, aggregate, context=None):
        return self.function(*self.args, **self.kwargs)


_functions = (
    AggregateFunction("sum", sql.functions.sum),
    AggregateFunction("min", sql.functions.min),
    AggregateFunction("max", sql.functions.max),
    AggregateFunction("count_nonempty", sql.functions.count),
    AggregateFunction("avg", avg),
    AggregateFunction("stddev", stddev),
    AggregateFunction("variance", variance),
    AggregateFunction("identity", lambda c: c),

    GenerativeFunction("count", sql.functions.count, 1),
)

_function_dict = {}


def _create_function_dict():
    if not _function_dict:
        for func in _functions:
            _function_dict[func.name] = func


def get_aggregate_function(name):
    """Returns an aggregate function `name`. The returned function takes two
    arguments: `aggregate` and `context`. When called returns a labelled
    SQL expression."""

    _create_function_dict()
    return _function_dict[name]


def available_aggregate_functions():
    """Returns a list of available aggregate function names."""
    _create_function_dict()
    return _function_dict.keys()

