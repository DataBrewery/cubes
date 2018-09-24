# -*- coding: utf-8 -*-

from __future__ import absolute_import

from collections import Iterable

from cubes_lite import compat
from cubes_lite.errors import ArgumentError
from cubes_lite.model import Model
from cubes_lite.model.utils import cached_property

__all__ = (
    'RequestType',
    'Request',
    'Response',
)


class RequestType(object):
    count = 'count'
    data = 'data'

    def __init__(
        self,
        type_,
        request_cls=None,
        response_cls=None,
        query_builder_cls_desc=None,
    ):
        """
        :param type_: str
        :param request_cls: Request
        :param response_cls: Response
        :param query_builder_cls_desc: QueryBuilder or dict with cubes names

        Examples of query_builder_cls_desc:

        # all queries with the same builder
        query_builder_cls_desc=SomeQueryBuilder

        # choose builder, base on request data
        query_builder_cls_desc={
            ('events',): EventsQueryBuilder,
            ('events', 'cohorts'): CohortsQueryBuilder,
            ('cohorts'): SimpleCohortsQueryBuilder,
        }
        """

        self.type_ = type_
        self.request_cls = request_cls
        self.response_cls = response_cls
        self.query_builder_cls_desc = query_builder_cls_desc


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
        self.offset = offset or 0

        self.options = options

        self._init()

    def _init(self):
        for condition in self.conditions:
            condition.bind(self.model)

    def __repr__(self):
        return '<Request({}: {})>'.format(self.model, self.conditions)

    @cached_property
    def drilldown_levels(self):
        result = []
        for dimension, levels in self.drilldown:
            dimension = self.model.get_dimension(dimension)
            if not isinstance(levels, (list, tuple)):
                levels = [levels]
            levels = [dimension.get_level(level) for level in levels]
            result.extend(levels)
        return result

    @cached_property
    def all_attributes(self):
        """Returns an unordered set of key attributes used in the request."""

        attributes = set()

        for c in self.conditions:
            attributes.update(c.all_attributes())

        attributes.update(self.aggregates)
        attributes.update(level.key for level in self.drilldown_levels)
        attributes.update(attr for attr, _ in self.order)

        return list(attributes)

    @cached_property
    def aggregates(self):
        """Prepares the attribute list for aggregations. If no aggregates
        are specified then all model's aggregates are returned.
        """

        if self._aggregates is None:
            return self.model.all_aggregates

        allowed_aggregates = {a.public_name: a for a in self.model.all_aggregates}
        aggregates = [
            allowed_aggregates[a]
            for a in self._aggregates
            if a in allowed_aggregates
        ]
        return aggregates

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

            attributes = self.model.get_aggregate_attributes([name])
            if attributes:
                attribute = attributes[0]
                result.append((attribute, direction))
                continue

            attributes = self.model.get_attributes([name])
            if attributes:
                attribute = attributes[0]
                result.append((attribute, direction))
                continue

            raise ArgumentError('Unknown attribute: "{}"'.format(name))

        return result

    def get_related_cubes(self):
        attributes = self.all_attributes
        return self.model.get_related_cubes(attributes)
