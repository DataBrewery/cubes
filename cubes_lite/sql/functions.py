# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import sqlalchemy.sql as sql
import sqlalchemy.sql.functions as funcs

from cubes_lite.errors import ModelError

__all__ = (
    'Function',
)


class Function(object):
    """
    Function description for aggregates.

    `coalesce_args` - the values will be coalesced to 0 before the aggregation
    `coalesce_result` - the aggregate will be coalesced to 0 before the aggregation
    """

    registry = {}

    @classmethod
    def register(cls, function):
        key = function.name.lower()
        if key in cls.registry:
            raise ValueError('Function "{}" already registered'.format(key))

        cls.registry[key] = function

    @classmethod
    def get(cls, name):
        name = name.lower()
        function = cls.registry.get(name)
        if function is None:
            raise ValueError('Function "{}" does not exist'.format(name))
        return function

    def __init__(
        self, name, action, min_args_count=1,
        coalesce_args=False, coalesce_result=False,
    ):
        self.name = name
        self.action = action
        self.min_args_count = min_args_count
        self._coalesce_args = coalesce_args
        self._coalesce_result = coalesce_result

        self.register(self)

    def __call__(self, aggregate, context, coalesce=False):
        """Applied the function on the aggregate and returns labelled
        expression. SQL expression label is the aggregate's name. This method
        calls `apply()` method which can be overriden by subclasses.
        """

        expression = self.apply(aggregate, context, coalesce)
        expression = expression.label(aggregate.public_name)
        return expression

    def coalesce_args(self, aggregate, args):
        """Coalesce the value before aggregation of `aggregate`. `value` is a
        SQLAlchemy expression."""

        default_missing_value = 0

        return [
            funcs.coalesce(arg, coalesce_to)
            for arg, coalesce_to in zip(
                args,
                [
                    # TODO: use missing_value of aggregate
                    default_missing_value
                    for a in aggregate.depends_on
                ]
            )
        ]

    def coalesce_aggregate(self, aggregate, value):
        """Coalesce the aggregated value of `aggregate`. `value` is a
        SQLAlchemy expression."""

        coalesce_to = 0
        if aggregate.missing_value is not None:
            coalesce_to = aggregate.missing_value
        return funcs.coalesce(value, coalesce_to)

    def apply(self, aggregate, context, coalesce=False):
        """Apply the function on the aggregate. Subclasses might override this
        method and use other `aggregates` and browser context.

        If `missing_value` is not `None`, then the aggregate's source value
        should be wrapped in ``COALESCE(column, missing_value)``.

        Returns a SQLAlchemy expression."""

        if not aggregate.depends_on:
            raise ModelError(
                'No dpendants specified for aggregate "{}", '
                'required for function "{}"'
                .format(aggregate, self.name)
            )

        if len(aggregate.depends_on) < self.min_args_count:
            raise ModelError(
                'Not enough dependants for aggregate "{}", '
                'function "{}", need at least "{}"'
                .format(aggregate, self.name, self.min_args_count)
            )

        columns = [
            context[a]
            for a in aggregate.depends_on[:self.min_args_count]
        ]

        if coalesce and self._coalesce_args:
            columns = self.coalesce_args(aggregate, columns)

        expression = self.action(*columns)

        if coalesce and self._coalesce_result:
            expression = self.coalesce_aggregate(aggregate, expression)

        return expression


class CountFunction(Function):
    def __init__(self, name, coalesce_result=False):
        super(CountFunction, self).__init__(
            name,
            action=None,
            min_args_count=0,
            coalesce_args=False,
            coalesce_result=coalesce_result,
        )

    def apply(self, aggregate, context=None, coalesce=False):
        expression = funcs.count(1)

        if coalesce and self._coalesce_result:
            expression = self.coalesce_aggregate(aggregate, expression)

        return expression


class avg(funcs.ReturnTypeFromArgs):
    pass


Function('sum', funcs.sum, coalesce_result=True)
CountFunction('count')
Function('count_nonempty', funcs.count, coalesce_result=True)
Function('count_distinct', lambda x: funcs.count(sql.expression.distinct(x)))
Function('min', funcs.min, coalesce_args=True)
Function('max', funcs.max, coalesce_args=True)
Function('avg', avg, coalesce_args=True)
Function(
    'fraction',
    action=lambda a, b: (1.0 * a) / sql.func.nullif(b, 0),
    min_args_count=2,
    coalesce_args=False,
    coalesce_result=True,
)
