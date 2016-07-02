# -*- encoding=utf -*-
"""SQL Browser"""

from __future__ import absolute_import

import collections

try:
    import sqlalchemy
    import sqlalchemy.sql as sql

except ImportError:
    from ...common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")

from ..statutils import available_calculators
from ..browser import AggregationBrowser, AggregationResult, Drilldown
from ..logging import get_logger
from ..errors import ArgumentError, InternalError
from ..stores import Store
from ..cells import Cell, PointCut
from ..model import collect_attributes
from .. import compat

from .functions import available_aggregate_functions
from .mapper import DenormalizedMapper, StarSchemaMapper, map_base_attributes
from .mapper import distill_naming
from .query import StarSchema, QueryContext, to_join, FACT_KEY_LABEL
from .utils import paginate_query, order_query


__all__ = [
    "SQLBrowser",
]


class SQLBrowser(AggregationBrowser):
    """SnowflakeBrowser is a SQL-based AggregationBrowser implementation that
    can aggregate star and snowflake schemas without need of having
    explicit view or physical denormalized table.

    Attributes:

    * `cube` - browsed cube
    * `store` - a `Store` object or a SQLAlchemy engine
    * `locale` - locale used for browsing
    * `debug` - output SQL to the logger at INFO level

    Other options in `kwargs`:
    * `metadata` – SQLAlchemy metadata, if `store` is an engine or a
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

    __description__ = """
    SQL - relational database browser (for ROLAP). Generates statements on top
    of star or snowflake schemas.
    """

    __options__ = [
        {
            "name": "include_summary",
            "description": "Include aggregation summary "\
                           "(requires extra statement)",
            "type": "bool"
        },
        {
            "name": "include_cell_count",
            "type": "bool"
        },
        {
            "name": "use_denormalization",
            "type": "bool"
        },
        {
            "name": "safe_labels",
            "description": "Use internally SQL statement column labels " \
                           "without special characters",
            "type": "bool"
        }

    ]

    def __init__(self, cube, store, locale=None, debug=False, **kwargs):
        """Create a SQL Browser."""

        super(SQLBrowser, self).__init__(cube, store)

        if not cube:
            raise ArgumentError("Cube for browser should not be None.")

        self.logger = get_logger()

        self.cube = cube
        self.locale = locale or cube.locale
        self.debug = debug

        # Database connection and metadata
        # --------------------------------

        if isinstance(store, Store):
            self.connectable = store.connectable
            metadata = store.metadata
        else:
            self.connectable = store

            metadata = kwargs.get("metadata",
                                  sqlalchemy.MetaData(bind=self.connectable))

        # Options
        # -------

        # Merge options with store options
        options = {}
        options.update(store.options)
        options.update(kwargs)

        self.include_summary = options.get("include_summary", True)
        self.include_cell_count = options.get("include_cell_count", True)

        self.safe_labels = options.get("safe_labels", False)
        if self.safe_labels:
            self.logger.debug("using safe labels for cube {}"
                              .format(cube.name))

        # Whether to ignore cells where at least one aggregate is NULL
        # TODO: this is undocumented
        self.exclude_null_agregates = options.get("exclude_null_agregates",
                                                  False)

        # Mapper
        # ------

        # Mapper is responsible for finding corresponding physical columns to
        # dimension attributes and fact measures. It also provides information
        # about relevant joins to be able to retrieve certain attributes.

        if options.get("is_denormalized", options.get("use_denormalization")):
            mapper = DenormalizedMapper
        else:
            mapper = StarSchemaMapper

        self.logger.debug("using mapper %s for cube '%s' (locale: %s)" %
                          (str(mapper.__name__), cube.name, locale))

        # Prepare the mappings of base attributes
        #
        naming = distill_naming(options)
        (fact_name, mappings) = map_base_attributes(cube, mapper,
                                                    naming=naming,
                                                    locale=locale)

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

        # Extract hierarchies
        # -------------------
        #
        self.hierarchies = self.cube.distilled_hierarchies

    def features(self):
        """Return SQL features. Currently they are all the same for every
        cube, however in the future they might depend on the SQL engine or
        other factors."""

        features = {
            "actions": ["aggregate", "fact", "members", "facts", "cell"],
            "aggregate_functions": available_aggregate_functions(),
            "post_aggregate_functions": available_calculators()
        }

        return features

    def is_builtin_function(self, funcname):
        """Returns `True` if the function `funcname` is backend's built-in
        function."""

        return funcname in available_aggregate_functions()

    def fact(self, key_value, fields=None):
        """Get a single fact with key `key_value` from cube.

        Number of SQL queries: 1."""

        (statement, labels) = self.denormalized_statement(attributes=fields,
                                                          include_fact_key=True)
        condition = statement.columns[FACT_KEY_LABEL] == key_value
        statement = statement.where(condition)

        cursor = self.execute(statement, "fact")
        row = cursor.fetchone()

        if row:
            # Convert SQLAlchemy object into a dictionary
            record = dict(zip(labels, row))
        else:
            record = None

        cursor.close()

        return record

    def facts(self, cell=None, fields=None, order=None, page=None,
              page_size=None, fact_list=None):
        """Return all facts from `cell`, might be ordered and paginated.

        `fact_list` is a list of fact keys to be selected. Might be used to
        fetch multiple facts using single query instead of multiple `fact()`
        queries.

        Number of SQL queries: 1.
        """
        attrs = self.cube.get_attributes(fields)
        cell = cell or Cell(self.cube)

        (statement, labels) = self.denormalized_statement(cell=cell,
                                                          attributes=attrs,
                                                          include_fact_key=True)

        if fact_list is not None:
            in_condition = self.star.fact_key_column.in_(fact_list)
            statement = statement.where(in_condition)

        statement = paginate_query(statement, page, page_size)

        # TODO: use natural order
        statement = order_query(statement,
                                order,
                                natural_order={},
                                labels=labels)

        cursor = self.execute(statement, "facts")

        return ResultIterator(cursor, labels)

    def test(self, aggregate=False):
        """Tests whether the statement can be constructed and executed. Does
        not return anything, but raises an exception if there are issues with
        the generated statements. By default it tests only denormalized
        statement by fetching one row. If `aggregate` is `True` then test also
        aggregation."""
        (statement, _) = self.denormalized_statement()
        statement = statement.limit(1)
        result = self.connectable.execute(statement)
        result.close()

        aggs = self.cube.all_aggregate_attributes
        dd = Drilldown()

        (statement, labels) = self.aggregation_statement(aggregates=aggs,
                                                         cell=Cell(self.cube),
                                                         drilldown=dd,
                                                         for_summary=True)
        result = self.connectable.execute(statement)
        result.close()

    def provide_members(self, cell, dimension, depth=None, hierarchy=None,
                        levels=None, attributes=None, page=None,
                        page_size=None, order=None):
        """Return values for `dimension` with level depth `depth`. If `depth`
        is ``None``, all levels are returned.

        Number of database queries: 1.
        """
        if not attributes:
            attributes = []
            for level in levels:
                attributes += level.attributes

        (statement, labels) = self.denormalized_statement(attributes, cell)
        # Order and paginate
        #
        statement = statement.group_by(*statement.columns)
        statement = order_query(statement,
                                order,
                                labels=labels)
        statement = paginate_query(statement, page, page_size)

        result = self.execute(statement, "members")

        return ResultIterator(result, labels)

    def path_details(self, dimension, path, hierarchy=None):
        """Returns details for `path` in `dimension`. Can be used for
        multi-dimensional "breadcrumbs" in a used interface.

        Number of SQL queries: 1.
        """
        dimension = self.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)

        cut = PointCut(dimension, path, hierarchy=hierarchy)
        cell = Cell(self.cube, [cut])

        attributes = []
        for level in hierarchy.levels[0:len(path)]:
            attributes += level.attributes

        (statement, labels) = self.denormalized_statement(attributes,
                                                          cell,
                                                          include_fact_key=True)
        statement = statement.limit(1)
        cursor = self.execute(statement, "path details")

        row = cursor.fetchone()

        if row:
            member = dict(zip(labels, row))
        else:
            member = None

        return member

    def execute(self, statement, label=None):
        """Execute the `statement`, optionally log it. Returns the result
        cursor."""
        self._log_statement(statement, label)
        return self.connectable.execute(statement)

    def provide_aggregate(self, cell, aggregates, drilldown, split, order,
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
        * `across`: list of other cubes to be drilled across

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
            if not (page_size and page is not None):
                self.assert_low_cardinality(cell, drilldown)

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

        # If exclude_null_aggregates is True then don't include cells where
        # at least one of the bult-in aggregates is NULL
        if result.cells is not None and self.exclude_null_agregates:
            native_aggs = [agg.ref for agg in aggregates
                           if agg.function and self.is_builtin_function(agg.function)]
            result.exclude_if_null = native_aggs

        return result

    def _create_context(self, attributes):
        """Create a query context for `attributes`. The `attributes` should
        contain all attributes that will be somehow involved in the query."""

        collected = self.cube.collect_dependencies(attributes)
        return QueryContext(self.star,
                            attributes=collected,
                            hierarchies=self.hierarchies,
                            parameters=None,
                            safe_labels=self.safe_labels)

    def denormalized_statement(self, attributes=None, cell=None,
                               include_fact_key=False):
        """Returns a tuple (`statement`, `labels`) representing denormalized
        star statement restricted by `cell`. If `attributes` is not specified,
        then all cube's attributes are selected. The returned `labels` are
        correct labels to be applied to the iterated result in case of
        `safe_labels`."""

        attributes = attributes or self.cube.all_fact_attributes

        refs = [attr.ref for attr in collect_attributes(attributes, cell)]
        context_attributes = self.cube.get_attributes(refs)
        context = self._create_context(context_attributes)

        if include_fact_key:
            selection = [self.star.fact_key_column]
        else:
            selection = []

        names = [attr.ref for attr in attributes]
        selection += context.get_columns(names)

        cell_condition = context.condition_for_cell(cell)

        statement = sql.expression.select(selection,
                                          from_obj=context.star,
                                          whereclause=cell_condition)

        return (statement, context.get_labels(statement.columns))

    # Aggregate
    # =========
    #
    # This is the reason of our whole existence.
    #
    def aggregation_statement(self, cell, aggregates, drilldown=None,
                              split=None, for_summary=False):
        """Builds a statement to aggregate the `cell` and reutrns a tuple
        (`statement`, `labels`). `statement` is a SQLAlchemy statement object,
        `labels` is a list of attribute names selected in the statement. The
        `labels` should be applied on top of the result iterator, since the
        real columns might have simplified labels when `safe_labels` is
        ``True``.

        * `cell` – `Cell` to aggregate
        * `aggregates` – list of aggregates to consider (should not be empty)
        * `drilldown` – an optional `Drilldown` object
        * `split` – split cell for split condition
        * `for_summary` – do not perform `GROUP BY` for the drilldown. The
          drilldown is used only for choosing tables to join
        """
        # * `across` – cubes that share dimensions

        # TODO: PTD

        # Basic assertions

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
        attributes = self.cube.get_attributes(refs, aggregated=True)
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

    def _log_statement(self, statement, label=None):
        label = "SQL(%s):" % label if label else "SQL:"
        self.logger.debug("%s\n%s\n" % (label, str(statement)))


class ResultIterator(object):
    """
    Iterator that returns SQLAlchemy ResultProxy rows as dictionaries
    """
    def __init__(self, result, labels):
        self.result = result
        self.batch = None
        self.labels = labels
        self.exclude_if_null = None

    def __iter__(self):
        while True:
            if not self.batch:
                many = self.result.fetchmany()
                if not many:
                    break
                self.batch = collections.deque(many)

            row = self.batch.popleft()

            if self.exclude_if_null \
                    and any(row[agg] is None for agg in self.exclude_if_null):
                continue

            yield dict(zip(self.labels, row))
