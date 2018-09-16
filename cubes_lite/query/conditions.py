# -*- coding: utf-8 -*-

from __future__ import absolute_import

__all__ = (
    'ConditionBase',
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
        return '<{}({} {}= {})>'.format(
            self.__class__.__name__,
            self.level.key,
            '!' if self.invert else '',
            self.value,
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

    def evaluate(self, **options):
        assert self.is_bound(), 'Should be bound to cube'

        raise NotImplementedError()
