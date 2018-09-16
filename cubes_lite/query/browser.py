# -*- coding: utf-8 -*-

from __future__ import absolute_import

from sqlalchemy.dialects import postgresql

from cubes_lite.errors import ArgumentError
from cubes_lite.loggers import get_logger

from .request import Request
from .query import QueryBuilder

__all__ = (
    'Browser',
)


logger = get_logger()


class Browser(object):
    """Class for browsing data aggregations

    :Attributes:
      * `model` - a set of cubes for browsing data
    """

    default_request_cls = Request
    default_query_builder_cls = QueryBuilder

    query_types_registry = {}

    log_queries = False

    def __init__(self, model, **options):
        super(Browser, self).__init__()

        if not model:
            raise ArgumentError('No model was given for aggregation browser')

        self.model = model
        self.log_queries = options.get('log_queries') or self.log_queries

        self._expand_query_types_registry()

    def _expand_query_types_registry(self):
        for type_, info in self.query_types_registry.items():
            if len(info) == 2:
                (request_cls, query_builders) = info
                response_cls = None
            elif len(info) == 3:
                (request_cls, query_builders, response_cls) = info
            else:
                raise ArgumentError(
                    'Wrong query_types description in "{}"'
                    .format(self.model)
                )

            request_cls = request_cls or self.default_request_cls
            response_cls = response_cls or request_cls.response_cls
            query_builders = query_builders or self.default_query_builder_cls

            self.query_types_registry[type_] = (
                request_cls,
                response_cls,
                query_builders,
            )

    def browse(
        self, request_type, conditions=None, aggregates=None,
        drilldown_levels=None,
        **options
    ):
        """
        Arguments:

        * `aggregates` - list of aggregate measures. By default all
          cube's aggregates are included in the result.
        * `drilldown_levels` - dimensions' levels through which to drill-down

        Returns a :class:`Response` object.
        """

        request_cls = self.get_request_cls(request_type)

        request = request_cls(
            self.model,
            type_=request_type,
            conditions=conditions,
            aggregates=aggregates,
            drilldown=drilldown_levels,
            **options
        )

        return self._browse(request)

    def _browse(self, request):
        query_builder = self.get_query_builder(request)
        query = query_builder.construct()
        meta_data = query_builder.get_meta_data()

        data = self.execute_query(query, label=str(request.type_))

        response_cls = self.get_response_cls(request.type_)
        return response_cls(request, data, **meta_data)

    def execute_query(self, query, label=None):
        if self.log_queries:
            label = 'SQL({}):'.format(label if label else 'info')
            query = query.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={'literal_binds': True},
            )
            logger.debug('%s\n%s\n', label, query)

        return self._execute_query(query)

    def _execute_query(self, statement):
        raise NotImplementedError()

    def get_query_builder(self, request):
        info = self.query_types_registry.get(request.type_)
        if not info:
            return self.default_query_builder_cls

        desc = info[2]
        if not isinstance(desc, dict):
            query_builder_cls = desc
        else:
            cubes = request.get_related_cubes()
            cube_names = [cube.name for cube in cubes]
            key = tuple(sorted(cube_names))

            query_builder_cls = desc.get(key) or self.default_query_builder_cls

        return query_builder_cls(request, self)

    def get_request_cls(self, request_type):
        info = self.query_types_registry.get(request_type)
        if not info:
            return self.default_request_cls
        return info[0]

    def get_response_cls(self, request_type):
        info = self.query_types_registry.get(request_type)
        if not info:
            return self.default_request_cls.response_cls
        return info[1]
