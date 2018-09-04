# -*- coding: utf-8 -*-

from __future__ import absolute_import

__all__ = (
    'PointCondition',
    'RangeCondition',
    'OptionalCondition',
)


class ConditionBase(object):
    def __init__(self, dimension, value, level=None, invert=False):
        self.dimension = dimension
        self.value = value
        self.level = level
        self.invert = invert

        self.model = None

    def bind(self, model):
        self.model = model

        if not self.dimension:
            return

        dimension = self.model.get_dimension(self.dimension)

        self.dimension = dimension
        self.level = dimension.get_level(self.level)

    def is_bound(self):
        return self.model is not None

    def __repr__(self):
        return '<{}({}:{} {}= {})>'.format(
            self.__class__.__name__,
            self.dimension, self.level,
            '!' if self.invert else '', self.value,
        )

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return (
            self.dimension == other.dimension and
            self.value == other.value and
            self.level == other.level and
            self.invert == other.invert
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def all_attributes(self):
        if not self.is_bound:
            return []

        return self._all_attributes()

    def _all_attributes(self):
        return [self.level.key]

    def evaluate(self):
        assert self.is_bound(), 'Should be bound to model'

        condition = self._evaluate()
        if self.invert:
            condition = condition.not_()
        return condition

    def _evaluate(self):
        raise NotImplementedError()


class PointCondition(ConditionBase):
    """Object describing way of slicing a cube through point in a dimension"""

    def __init__(self, dimension, value, level=None, invert=False):
        if not isinstance(value, list):
            value = [value]

        super(PointCondition, self).__init__(dimension, value, level, invert)

    def _evaluate(self):
        raise NotImplementedError()


class RangeCondition(ConditionBase):
    """Object describing way of slicing a cube (cell) between two points of a
    dimension that has ordered points. For dimensions with unordered points
    behaviour is unknown."""

    def __init__(self, dimension, (from_, to_), level=None, invert=False):
        super(RangeCondition, self).__init__(dimension, (from_, to_), level, invert)

    @property
    def from_(self):
        return self.value[0]

    @property
    def to_(self):
        return self.value[1]

    def _evaluate(self):
        raise NotImplementedError()


class OptionalCondition(ConditionBase):
    def __init__(self, values, invert=False):
        assert isinstance(values, list), 'Should be a list of Conditions'
        super(OptionalCondition, self).__init__(None, values, None, invert)

    def _all_attributes(self):
        result = []
        for condition in self.value:
            attrs = condition._all_attributes()
            result.extend(attrs)
        return result

    def _evaluate(self):
        raise NotImplementedError()
