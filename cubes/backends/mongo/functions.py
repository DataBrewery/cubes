# -*- encoding=utf -*-

from __future__ import absolute_import

from collections import namedtuple
from ...errors import *

try:
    import sqlalchemy
    import sqlalchemy.sql as sql
    from sqlalchemy.sql.functions import ReturnTypeFromArgs
except ImportError:
    from ...common import MissingPackage
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


_aggregate_functions = {
    'count': {
        'group_by': (lambda field: { '$sum': 1 }),
        'aggregate_fn': len,
    },
    'sum': {
        'group_by': (lambda field: { '$sum': "$%s" % field }),
        'aggregate_fn': sum,
    },
    'first': {
        'group_by': (lambda field: { '$first': "$%s" % field }),
        'aggregate_fn': None,                                       # Is this used?
    },
    'last': {
        'group_by': (lambda field: { '$last': "$%s" % field }),
        'aggregate_fn': None,                                       # Is this used?
    },
    'custom': {
        'group_by' : (lambda field: { '$sum': 1 }),
        'aggregate_fn': len
    }
}


class MongoAggregationFunction(object):
    def __init__(self, name, function, group_by):
        """Creates a MongoDB aggregation function. `name` is the function name,
        `function` is the function for aggregation and `group_by` is a callable
        object that """

        self.name = name
        self.function = function
        self.group_by = group_by


def get_aggregate_function(name):
    """Returns an aggregate function `name`. The returned function takes two
    arguments: `aggregate` and `context`. When called returns a labelled
    SQL expression."""

    name = name or "identity"
    return _aggregate_functions[name]

def available_aggregate_functions():
    """Returns a list of available aggregate function names."""
    return _aggregate_functions.keys()


