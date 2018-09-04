# -*- coding: utf-8 -*-

from __future__ import absolute_import

from common import FactoryMixin
from ..errors import ArgumentError
from ..loggers import get_logger

from .result import Request

__all__ = (
    'Browser',
)


logger = get_logger()


class Browser(object):
    """Class for browsing data aggregations

    :Attributes:
      * `model` - a set of cubes for browsing data
    """

    request_cls = Request
    query_builder_cls = QueryBuilder

    def __init__(self, model, **options):
        super(Browser, self).__init__()

        if not model:
            raise ArgumentError('No model was given for aggregation browser')

        self.model = model

    def browse(
        self, request_type, conditions=None, aggregates=None,
        drilldown_levels=None, order=None, limit=None, offset=None,
        **options
    ):
        """
        Arguments:

        * `aggregates` - list of aggregate measures. By default all
          cube's aggregates are included in the result.
        * `drilldown_levels` - dimensions' levels through which to drill-down
        * `order` - attribute order specification (see below)
        * `page` - page index when requesting paginated results
        * `page_size` - number of result items per page

        Returns a :class:`Response` object.
        """

        request = self.request_cls.build(
            self.model,
            type_=request_type,
            conditions=conditions,
            aggregates=aggregates,
            drilldown_levels=drilldown_levels,
            order=order,
            limit=limit,
            offset=offset,
            **options
        )

        return self._browse(request)

    def _browse(self, request):
        query = self.build_query(request)
        data = self.execute_query(query, label=str(request.type_))
        return request.response_cls(request, data)

    def execute_query(self, query, label=None):
        label = 'SQL({}):'.format(label if label else 'info')
        logger.debug('%s\n%s\n', label, str(query))

        return self._execute_query(query)

    def _execute_query(self, statement):
        raise NotImplementedError()

    def build_query(self, request):
        cubes = self.model.get_related_cubes(request._aggregates)
        cube_names = [cube.name for cube in cubes]
        query_builder = self.query_builder_cls.build(request, cube_names)
        return query_builder.construct()


class QueryBuilder(FactoryMixin):
    def __init__(self, request):
        self.request = request
        self.model = request.model

    @classmethod
    def factory_key(cls, params):
        return params.request.type_, tuple(sorted(params.cubes_names))

    @classmethod
    def on_building(cls, cls_to_create, params):
        params.pop('cubes_names')
        return cls_to_create(**params)

    @classmethod
    def registry(cls):
        return cls

    def construct(self):
        raise NotImplementedError()
