# -*- coding: utf-8 -*-

from __future__ import absolute_import

from cubes_lite.errors import ArgumentError

__all__ = (
    'ConditionBase',
)


class ConditionBase(object):
    def __init__(self, attribute, value, invert=False, value_func=None, **options):
        self.attribute = attribute
        self.value = value
        self.invert = invert
        self.value_func = value_func

        self.options = options

        self.model = None

    def _get_attribute(self):
        assert self.is_bound(), 'Should be bound to cube'

        dimension = self.model.get_dimension(self.attribute)
        if dimension:
            level = dimension.get_level(self.options.get('level'))
            return level.key

        aggregates = self.model.get_aggregate_attributes([self.attribute])
        if not aggregates:
            raise ArgumentError('Unknown attribute "{}"'.format(self.attribute))

        return aggregates[0]

    def bind(self, model):
        self.model = model

        if not self.attribute:
            return

        self.attribute = self._get_attribute()

    def is_bound(self):
        return self.model is not None

    def __repr__(self):
        return '<{}({} {}= {})>'.format(
            self.__class__.__name__,
            self.attribute,
            '!' if self.invert else '',
            self.value,
        )

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return (
            self.attribute == other.attribute and
            self.value == other.value and
            self.invert == other.invert and
            self.options == other.options
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def all_attributes(self):
        if not self.is_bound:
            return []

        return self._all_attributes()

    def _all_attributes(self):
        return [self.attribute]

    def evaluate(self, **options):
        assert self.is_bound(), 'Should be bound to cube'

        raise NotImplementedError()

    def get_value(self):
        if self.value_func is None:
            return self.value

        if isinstance(self.value, tuple):
            return tuple(self.value_func(v) for v in self.value)

        return self.value_func(self.value)
