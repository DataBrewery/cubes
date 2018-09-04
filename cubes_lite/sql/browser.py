# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import collections

import sqlalchemy
import sqlalchemy.sql as sql

from ..query import Browser
from ..query.browser import QueryBuilder
from ..loggers import get_logger
from ..errors import ArgumentError, InternalError
from ..stores import Store
from ..model.logic import collect_attributes
from .. import compat

from .mapping import Mapper
from .query import StarSchema, QueryContext
from .utils import paginate_query, order_query

__all__ = (
    'SQLBrowser',
)


logger = get_logger()


class RequestType(object):
    total = 'total'
    data = 'data'


class SQLQueryBuilder(QueryBuilder):
    @classmethod
    def registry(cls):
        return {
            RequestType.total: TotalSQLQueryBuilder,
            RequestType.data: DataSQLQueryBuilder,
        }


class TotalSQLQueryBuilder(SQLQueryBuilder):
    def construct(self):
        pass


class DataSQLQueryBuilder(SQLQueryBuilder):
    def construct(self):
        pass


class SQLBrowser(Browser):
    """SQL-based Browser implementation that
    can aggregate star and snowflake schemas.

    Attributes:

    * `cube` - browsed cube
    * `store` - a `Store` object or a SQLAlchemy engine
    * `locale` - locale used for browsing
    * `debug` - output SQL to the logger at INFO level

    Other options in `kwargs`:
    * `model` – SQLAlchemy model, if `store` is an engine or a
       connection (not a `Store` object)
    * `tables` – tables and/or table expressions used in the star schema
      (refer to the :class:`StarSchema` for more information)
    * `options` - passed to the mapper

    Tuning:

    * `include_summary` - it ``True`` then summary is included in
      aggregation result. Turned on by default.
    * `include_cell_count` – if ``True`` then total cell count is included
      in aggregation result. Turned on by default.
      performance reasons
    * `safe_labels` – safe labelling of the attributes in databases which
      don't allow characters such as ``.`` dots in column names

    Limitations:

    * only one locale can be used for browsing at a time
    * locale is implemented as denormalized: one column for each language
    """

    query_builder_cls = SQLQueryBuilder

    mapper_cls = Mapper

    def __init__(self, model, **kwargs):
        super(SQLBrowser, self).__init__(model)

        # Database connection and model
        # --------------------------------

        if isinstance(store, Store):
            self.connectable = store.connectable
            metadata = store.metadata
        else:
            self.connectable = store

            metadata = kwargs.get("model",
                                  sqlalchemy.MetaData(bind=self.connectable))

        # Options
        # -------

        # Merge options with store options
        options = {}
        options.update(store.options)
        options.update(kwargs)

        # Prepare the mappings of base attributes
        #
        fact_name = cube.ref
        mappings = self.mapper_cls(cube).get_mapping()

        tables = options.get("tables")

        # Prepare Join objects
        if cube.joins:
            joins = [to_join(join) for join in cube.joins]
        else:
            joins = []

        self.star = StarSchema(self.cube.name,
                               metadata,
                               mappings=mappings,
                               fact=fact_name,
                               joins=joins,
                               schema=naming.schema,
                               tables=tables)

    def _create_context(self, attributes):
        """Create a query context for `attributes`. The `attributes` should
        contain all attributes that will be somehow involved in the query."""

        collected = self.cube.collect_dependencies(attributes)
        return QueryContext(self.star,
                            attributes=collected,
                            hierarchies=self.hierarchies,
                            parameters=None,
                            safe_labels=self.safe_labels)

    def _execute_query(self, query):
        return self.connectable.execute(query)

    def build_query(self, cell, aggregates, drilldown, split, order,
                    page, page_size, **options):
        """Return aggregated result.

        Arguments:

        * `cell`: cell to be aggregated
        * `measures`: aggregates of these measures will be considered
        * `aggregates`: aggregates to be considered
        * `drilldown`: list of dimensions or list of tuples: (`dimension`,
          `hierarchy`, `level`)
        * `split`: an optional cell that becomes an extra drilldown segmenting
          the data into those within split cell and those not within
        * `attributes`: list of attributes from drilled-down dimensions to be
          returned in the result
        * `across`: list of other cubes_lite to be drilled across

        Query tuning:

        * `include_cell_count`: if ``True`` (``True`` is default) then
          `result.total_cell_count` is
          computed as well, otherwise it will be ``None``.
        * `include_summary`: if ``True`` (default) then summary is computed,
          otherwise it will be ``None``

        Result is paginated by `page_size` and ordered by `order`.

        Number of database queries:

        * without drill-down: 1 – summary
        * with drill-down (default): 3 – summary, drilldown, total drill-down
          record count

        Notes:

        * measures can be only in the fact table

        """

        # TODO: implement reminder

        result = AggregationResult(cell=cell, aggregates=aggregates,
                                   drilldown=drilldown,
                                   has_split=split is not None)

        # Summary
        # -------

        if self.include_summary or not (drilldown or split):
            (statement, labels) = self.aggregation_statement(cell,
                                                             aggregates=aggregates,
                                                             drilldown=drilldown,
                                                             for_summary=True)

            cursor = self.execute(statement, "aggregation summary")
            row = cursor.first()

            if row:
                # Convert SQLAlchemy object into a dictionary
                record = dict(zip(labels, row))
            else:
                record = None

            result.summary = record

        # Drill-down
        # ----------
        #
        # Note that a split cell if present prepends the drilldown

        if drilldown or split:
            result.levels = drilldown.result_levels(include_split=bool(split))
            natural_order = drilldown.natural_order

            self.logger.debug("preparing drilldown statement")

            (statement, labels) = self.aggregation_statement(cell,
                                                             aggregates=aggregates,
                                                             drilldown=drilldown,
                                                             split=split)
            # Get the total cell count before the pagination
            #
            if self.include_cell_count:
                count_statement = statement.alias().count()
                counts = self.execute(count_statement)
                result.total_cell_count = counts.scalar()

            # Order and paginate
            #
            statement = order_query(statement,
                                    order,
                                    natural_order,
                                    labels=labels)
            statement = paginate_query(statement, page, page_size)

            cursor = self.execute(statement, "aggregation drilldown")

            result.cells = ResultIterator(cursor, labels)
            result.labels = labels

        return result

    def aggregation_statement(self, cell, aggregates, drilldown=None,
                              split=None, for_summary=False):
        if not aggregates:
            raise ArgumentError("List of aggregates should not be empty")

        if not isinstance(drilldown, Drilldown):
            raise InternalError("Drilldown should be a Drilldown object. "
                                "Is '{}'".format(type(drilldown)))

        # 1. Gather attributes
        #

        self.logger.debug("prepare aggregation statement. cell: '%s' "
                          "drilldown: '%s' for summary: %s" %
                          (",".join([compat.to_unicode(cut) for cut in cell.cuts]),
                           drilldown, for_summary))

        # TODO: it is verylikely that the _create_context is not getting all
        # attributes, for example those that aggregate depends on
        refs = collect_attributes(aggregates, cell, drilldown, split)
        attributes = self.cube.get_attributes(refs)
        context = self._create_context(attributes)

        # Drilldown – Group-by
        # --------------------
        #
        # SELECT – Prepare the master selection
        #     * master drilldown items

        selection = context.get_columns([attr.ref for attr in
                                         drilldown.all_attributes])

        # SPLIT
        # -----
        if split:
            selection.append(context.column_for_split(split))

        # WHERE
        # -----
        condition = context.condition_for_cell(cell)

        group_by = selection[:] if not for_summary else None

        # TODO: coalesce if there are outer joins
        # TODO: ignore post-aggregations
        aggregate_cols = context.get_columns([agg.ref for agg in aggregates])

        if for_summary:
            # Don't include the group-by part (see issue #157 for more
            # information)
            selection = aggregate_cols
        else:
            selection += aggregate_cols

        statement = sql.expression.select(selection,
                                          from_obj=context.star,
                                          use_labels=True,
                                          whereclause=condition,
                                          group_by=group_by)

        return (statement, context.get_labels(statement.columns))




class ResultIterator(object):
    """
    Iterator that returns SQLAlchemy ResultProxy rows as dictionaries
    """

    def __init__(self, result, labels):
        self.result = result
        self.batch = None
        self.labels = labels
        self.exclude_if_null = []

    def __iter__(self):
        while True:
            if not self.batch:
                many = self.result.fetchmany()
                if not many:
                    break
                self.batch = collections.deque(many)

            row = self.batch.popleft()

            if any(row[agg] is None for agg in self.exclude_if_null):
                continue

            yield dict(zip(self.labels, row))
