# -*- coding: utf-8 -*-

from __future__ import absolute_import

import sqlalchemy.sql as sql

from cubes_lite.model.utils import cached_property
from cubes_lite.query.conditions import ConditionBase as ConditionBase_

__all__ = (
    'PointCondition',
    'MatchCondition',
    'RangeCondition',
    'OptionalCondition',
)


class ConditionBase(ConditionBase_):
    def evaluate(self, mapper):
        assert self.is_bound(), 'Should be bound to model'

        condition = self._evaluate(mapper)
        if self.invert:
            condition = sql.expression.not_(condition)
        return condition

    def _evaluate(self, mapper):
        raise NotImplementedError()


class PointCondition(ConditionBase):
    """Object describing way of slicing a cube through point in a dimension"""

    def __init__(self, dimension, value, level=None, invert=False):
        if not isinstance(value, (list, tuple)):
            value = [value]

        super(PointCondition, self).__init__(dimension, value, level, invert)

    def _evaluate(self, mapper):
        column = mapper.get_column_by_attribute(self.level.key)
        conditions = [(column == v) for v in self.value]
        return sql.expression.or_(*conditions)


class MatchCondition(ConditionBase):
    def _evaluate(self, mapper):
        column = mapper.get_column_by_attribute(self.level.key)
        return column.like(self.value)


class RangeCondition(ConditionBase):
    """Object describing way of slicing a cube between two points of a
        dimension that has ordered points. For dimensions with unordered points
        behaviour is unknown."""

    def __init__(self, dimension, (from_, to_), level=None, invert=False, strong=False):
        super(RangeCondition, self).__init__(dimension, (from_, to_), level, invert)
        self.strong = strong

    @cached_property
    def from_(self):
        return self.value[0]

    @cached_property
    def to_(self):
        return self.value[1]

    def _evaluate(self, mapper):
        column = mapper.get_column_by_attribute(self.level.key)

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
        super(OptionalCondition, self).__init__(None, values, None, invert)

        self.options = options

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
