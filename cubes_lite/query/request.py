# -*- coding: utf-8 -*-

from __future__ import absolute_import

from collections import Iterable

from .. import compat
from ..errors import ArgumentError
from ..model import Model
from ..model.utils import cached_property

__all__ = (
    'Request',
    'Response',
)


class Request(object):
    response_cls = Response

    def __init__(
        self, model, type_, conditions=None, aggregates=None, drilldown=None,
        order=None, limit=None, offset=None,
        **options
    ):
        if not isinstance(model, Model):
            raise ArgumentError(
                'Request cube should be subclass of Cube, provided: "{}"'
                .format(type(model).__name__)
            )

        self.model = model

        self.type_ = type_
        self.conditions = conditions or []
        self._aggregates = aggregates or []
        self.drilldown = drilldown or []
        self._order = order or []
        self.limit = limit
        self.offset = offset

        self.options = options

    def __repr__(self):
        return '<Request({}: {})>'.format(self.model, self.conditions)

    @cached_property
    def drilldown_levels(self):
        result = []
        for dimension, levels in self.drilldown:
            dimension = self.model.get_dimension(dimension)
            levels = [dimension.get_level(level) for level in levels]
            result.extend(levels)
        return result

    @cached_property
    def all_attributes(self):
        """Returns an unordered set of key attributes used in the request."""

        attributes = set()

        for c in self.conditions:
            attributes.update(c.all_attributes())

        attributes.update(self.all_aggregates())
        attributes.update(level.key for level in self.drilldown_levels)
        attributes.update(attr for attr, _ in self.order())

        return list(attributes)

    @cached_property
    def all_aggregates(self):
        """Prepares the attribute list for aggregations. If no aggregates
        are specified then all model's aggregates are returned.
        """

        aggregates = [self.model.get_aggregate(a) for a in self._aggregates]
        return aggregates or self.model.all_aggregates

    @cached_property
    def order(self):
        """Prepares an order list. Returns list of tuples (`attribute`,
        `order_direction`). `attribute` is cube's attribute object."""

        result = []
        for item in self._order:
            if isinstance(item, compat.string_type):
                name = item
                direction = 'asc'
            else:
                name, direction = item[0:2]

            attribute = self.model.get_attributes([name])
            if attribute:
                result.append((attribute, direction))

        return result

    def get_related_cubes(self):
        attributes = self.all_attributes
        return self.model.get_related_cubes(attributes)


class Response(object):
    def __init__(self, request, data=None, **meta_data):
        super(Response, self).__init__()

        self.request = request
        self._data = data

        for key, value in meta_data.items():
            setattr(self, key, value)

    def __iter__(self):
         data = self._data or []
         if not isinstance(data, Iterable):
             data = [data]
         return iter(data)

    @property
    def data(self):
        return list(self)
