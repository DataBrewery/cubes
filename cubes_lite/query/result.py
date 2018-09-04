# -*- coding: utf-8 -*-

from __future__ import absolute_import

from .. import compat
from ..common import FactoryMixin
from ..errors import ArgumentError
from ..model import Model
from ..model.utils import cached_property

__all__ = (
    'Request',
    'Response',
)


class Request(FactoryMixin):
    response_cls = Response

    def __init__(
        self, model, type_, conditions=None, aggregates=None, drilldown_levels=None,
        order=None, limit=None, offset=None,
        **options
    ):
        if not isinstance(model, Model):
            raise ArgumentError(
                'Request cube should be sublcass of Cube, provided: "{}"'
                .format(type(model).__name__)
            )

        self.model = model

        self.type_ = type_
        self.conditions = conditions or []
        self._aggregates = aggregates or []
        self.drilldown_levels = drilldown_levels or []
        self.order = order or []
        self.limit = limit
        self.offset = offset

        self.options = options

    @classmethod
    def factory_key(cls, params):
        return params.type_

    @classmethod
    def registry(cls):
        return cls

    def __repr__(self):
        return '<Request({}: {})>'.format(self.model, self.conditions)

    @cached_property
    def all_attributes(self):
        """Returns an unordered set of key attributes used in the request."""

        attributes = set()

        for c in self.conditions:
            attributes.update(c.all_attributes())

        attributes.update(self.all_aggregates())
        attributes.update(level.key for level in self.drilldown_levels)
        attributes.update(attr for attr, _ in self.get_order())

        return list(attributes)

    @cached_property
    def all_aggregates(self):
        """Prepares the attribute list for aggregations. If no aggregates
        are specified then all model's aggregates are returned.
        """

        aggregates = [self.model.get_aggregate(a) for a in self._aggregates]
        return aggregates or self.model.all_aggregates

    def get_order(self):
        """Prepares an order list. Returns list of tuples (`attribute`,
        `order_direction`). `attribute` is cube's attribute object."""

        result = []
        for item in self.order:
            if isinstance(item, compat.string_type):
                name = item
                direction = 'asc'
            else:
                name, direction = item[0:2]

            attribute = self.model.get_attributes(name)
            if attribute:
                result.append((attribute, direction))

        # TODO: merge drilldown_order here

        return result

    @property
    def drilldown_order(self):
        """Return a natural order for the drilldown. This order can be merged
        with user-specified order. Returns a list of tuples:
        (`attribute_name`, `order`)."""

        return [
            (
                level.order_attribute or level.key,
                level.order or 'asc'
            )
            for level in self.drilldown_levels
        ]


class Response(object):
     def __init__(self, request, data=None):
        super(Response, self).__init__()

        self.request = request
        self.data = data or []

     def __iter__(self):
        return iter(self.data)
