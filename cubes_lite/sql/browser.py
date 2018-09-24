# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import sqlalchemy

from cubes_lite.loggers import get_logger
from cubes_lite.query import Browser, RequestType

from .mapping import Mapper
from .request import ListSQLRequest, OneRowSQLRequest
from .query import SQLQueryBuilder, SummarySQLQueryBuilder, DataSQLQueryBuilder

__all__ = (
    'SQLBrowser',
)


logger = get_logger()


class Connection(object):
    """
    Relational database connection.
    """

    def __init__(self, url, **options):
        """
        * `url` - database URL (ex: ``postgresql://user:password@host:port/database``)
        * `options` - sqlalchemy options
            - case_sensitive
            - case_insensitive
            - convert_unicode
            - echo
            - echo_pool
            - implicit_returning
            - label_length
            - max_overflow
            - pool_size
            - pool_recycle
            - pool_timeout
            - supports_unicode_binds
        """

        self.connectable = sqlalchemy.create_engine(url, **options)

        # Load model here. This might be too expensive operation to be
        # performed on every request, therefore it is recommended to have one
        # shared open store per process. SQLAlchemy will take care about
        # necessary connections.

        self.metadata = sqlalchemy.MetaData(bind=self.connectable)


class SQLBrowser(Browser):
    """SQL-based Browser implementation that can aggregate star and
    snowflake schemas."""

    default_request_cls = ListSQLRequest
    default_query_builder_cls = SQLQueryBuilder

    connection_cls = Connection
    mapper_cls = Mapper

    query_types_registry = [
        RequestType(
            RequestType.count,
            request_cls=OneRowSQLRequest,
            query_builder_cls_desc=SummarySQLQueryBuilder,
        ),
        RequestType(
            RequestType.data,
            request_cls=ListSQLRequest,
            query_builder_cls_desc=DataSQLQueryBuilder,
        ),
    ]

    def __init__(self, model, url, connection_options, **options):
        super(SQLBrowser, self).__init__(model, **options)

        self.connection = self.connection_cls(url, **connection_options)
        self.mappers = {
            cube.name: self.mapper_cls(cube, metadata=self.connection.metadata)
            for cube in self.model.cubes
        }

    def _execute_query(self, query):
        return self.connection.connectable.execute(query)
