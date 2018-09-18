# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from collections import OrderedDict

from sqlalchemy import sql as sql

from cubes_lite import loggers
from cubes_lite.query.query import QueryBuilder
from cubes_lite.errors import ArgumentError


logger = loggers.get_logger(__name__)


class SQLQueryBuilder(QueryBuilder):
    def get_meta_data(self, query):
        return {'labels': [c.name for c in query.columns]}

    @staticmethod
    def order_column(column, order):
        """Orders a `column` according to `order` specified as string. Returns a
        `Column` expression"""

        if not order:
            return column

        if order.lower().startswith('asc'):
            return column.asc()

        if order.lower().startswith('desc'):
            return column.desc()

        raise ArgumentError(
            'Unknown order "{}" for column "{}"'.format(order, column)
        )

    @staticmethod
    def order_query(statement, order, columns=None, mapper=None):
        """Returns a SQL statement which is ordered according to the `order`.

        * `statement` - statement to be ordered
        * `order` explicit order, list of tuples (`attribute`, `direction`)
        """

        if not order:
            return statement

        final_order = OrderedDict()
        for attribute, direction in order:
            name = attribute.ref
            if name not in final_order:
                source_column = None
                if mapper:
                    source_column = mapper.get_column_by_attribute(attribute)
                if columns:
                    source_column = columns[name]
                if source_column is None:
                    raise  ValueError('No such column: "{}"'.format(name))

                column = SQLQueryBuilder.order_column(source_column, direction)
                final_order[name] = column

        statement = statement.order_by(*final_order.values())
        return statement

    def evaluate_conditions(self, mapper, conditions):
        conditions = [c.evaluate(mapper) for c in conditions]
        conditions = sql.expression.and_(*conditions)
        return conditions

    def construct_statement(
        self, all_attributes, aggregates, conditions=None, drilldown_levels=None,
    ):
        if not aggregates:
            raise ArgumentError('List of aggregates should not be empty')

        conditions = conditions or []
        drilldown_levels = drilldown_levels or []

        # the only mapper for single cube
        mapper = self.browser.mappers.values()[0]

        attributes = self.model.collect_dependencies(all_attributes)
        from_obj = mapper.get_joined_tables_for(attributes)

        attrs_to_group_by = [level.key for level in drilldown_levels]
        group_by_columns = [
            mapper.get_column_by_attribute(a)
            for a in attrs_to_group_by
        ]

        conditions = self.evaluate_conditions(mapper, conditions)

        aggregates_columns = mapper.compile_aggregates(aggregates)
        selection = group_by_columns + aggregates_columns

        statement = sql.expression.select(
            columns=selection,
            from_obj=from_obj,
            whereclause=conditions,
            group_by=group_by_columns,
            use_labels=True,
        )

        return statement


class SummarySQLQueryBuilder(SQLQueryBuilder):
    def construct(self):
        statement = self.construct_statement(
            all_attributes=self.request.all_attributes,
            conditions=self.request.conditions,
            aggregates=self.request.aggregates,
        )
        return statement


class DataSQLQueryBuilder(SQLQueryBuilder):
    def construct(self):
        statement = self.construct_statement(
            all_attributes=self.request.all_attributes,
            conditions=self.request.conditions,
            aggregates=self.request.aggregates,
            drilldown_levels=self.request.drilldown_levels,
        )

        statement = self.order_query(statement, self.request.order)

        if self.request.limit is not None and self.request.offset is not None:
            statement = statement.offset(self.request.offse)
            statement = statement.limit(self.request.limit)

        return statement
