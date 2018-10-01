# -*- coding: utf-8 -*-

from __future__ import absolute_import

import collections

import sqlalchemy.sql as sql

from cubes_lite.model.utils import cached_property
from cubes_lite.query.conditions import ConditionBase as ConditionBase_
from cubes_lite.sql.mapping import Mapper

__all__ = (
    'PointCondition',
    'MatchCondition',
    'RangeCondition',
    'OptionalCondition',
)


class ConditionBase(ConditionBase_):
    def evaluate(self, mapper):
        assert self.is_bound(), 'Should be bound to model'

        column = self._get_column(mapper)
        condition = self._evaluate(column)
        if self.invert:
            condition = sql.expression.not_(condition)
        return condition

    def _get_column(self, mapper):
        if not isinstance(mapper, (Mapper, dict)):
            return mapper

        if not self.attribute:
            return None

        if isinstance(mapper, dict):
            column = mapper[str(self.attribute)]
        else:
            column = mapper.get_column_by_attribute(self.attribute)

        return column

    def _evaluate(self, column):
        raise NotImplementedError()


class PointCondition(ConditionBase):
    """Object describing way of slicing a cube through point in a dimension"""

    def __init__(self, dimension, value, invert=False, **options):
        if isinstance(value, basestring):
            value = [value]

        if isinstance(value, collections.Iterable):
            value = list(value)

        if not isinstance(value, (list, tuple)):
            value = [value]

        super(PointCondition, self).__init__(dimension, value, invert, **options)

    def _evaluate(self, column):
        conditions = [(column == v) for v in self.value]
        return sql.expression.or_(*conditions)


class MatchCondition(ConditionBase):
    def _evaluate(self, column):
        return column.like(self.value)


class RangeCondition(ConditionBase):
    """Object describing way of slicing a cube between two points of a
        dimension that has ordered points. For dimensions with unordered points
        behaviour is unknown."""

    def __init__(self, dimension, (from_, to_), invert=False, strong=False, **options):
        super(RangeCondition, self).__init__(dimension, (from_, to_), invert, **options)
        self.strong = strong

    @cached_property
    def from_(self):
        return self.value[0]

    @cached_property
    def to_(self):
        return self.value[1]

    def _evaluate(self, column):
        upper_operator = sql.operators.gt if self.strong else sql.operators.ge
        lower_operator = sql.operators.lt if self.strong else sql.operators.le

        conditions = []
        if self.from_ is not None:
            conditions.append(upper_operator(column, self.from_))
        if self.to_ is not None:
            conditions.append(lower_operator(column, self.to_))

        return sql.expression.and_(*conditions)


class OptionalCondition(ConditionBase):
    def __init__(self, values, invert=False, **options):
        assert isinstance(values, list), 'Should be a list of Conditions'
        super(OptionalCondition, self).__init__(None, values, invert, **options)

    def __repr__(self):
        return '<{}({})>'.format(
            self.__class__.__name__,
            self.value,
        )

    def bind(self, model):
        self.model = model
        for child in self.value:
            child.bind(model)

    def _all_attributes(self):
        result = []
        for condition in self.value:
            attrs = condition._all_attributes()
            result.extend(attrs)
        return result

    def _evaluate(self, mapper):
        conditions = [v.evaluate(mapper) for v in self.value]
        return sql.expression.or_(*conditions)

    def _get_column(self, mapper):
        return mapper
