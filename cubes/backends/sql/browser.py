# -*- encoding=utf -*-
# Actually, this is a furry snowflake, not a nice star

from __future__ import absolute_import

from ...browser import *
from ...logging import get_logger
from ...statutils import calculators_for_aggregates, available_calculators
from ...errors import *
from .mapper import SnowflakeMapper, DenormalizedMapper
from .functions import get_aggregate_function, available_aggregate_functions
from .query import QueryBuilder

import itertools
import collections

try:
    import sqlalchemy
    import sqlalchemy.sql as sql

except ImportError:
    from ...common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")

__all__ = [
    "SnowflakeBrowser",
]


class SnowflakeBrowser(AggregationBrowser):
    __options__ = [
        {
            "name": "include_summary",
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
            "type": "bool"
        }

    ]

    def __init__(self, cube, store, locale=None, debug=False, **options):
        """SnowflakeBrowser is a SQL-based AggregationBrowser implementation that
        can aggregate star and snowflake schemas without need of having
        explicit view or physical denormalized table.

        Attributes:

        * `cube` - browsed cube
        * `locale` - locale used for browsing
        * `metadata` - SQLAlchemy MetaData object
        * `debug` - output SQL to the logger at INFO level
        * `options` - passed to the mapper and context (see their respective
          documentation)

        Tuning:

        * `include_summary` - it ``True`` then summary is included in
          aggregation result. Turned on by default.
        * `include_cell_count` – if ``True`` then total cell count is included
          in aggregation result. Turned on by default.
          performance reasons

        Limitations:

        * only one locale can be used for browsing at a time
        * locale is implemented as denormalized: one column for each language

        """
        super(SnowflakeBrowser, self).__init__(cube, store)

        if not cube:
            raise ArgumentError("Cube for browser should not be None.")

        self.logger = get_logger()

        self.cube = cube
        self.locale = locale or cube.locale
        self.debug = debug

        # Database connection and metadata
        # --------------------------------

        self.connectable = store.connectable
        self.metadata = store.metadata or sqlalchemy.MetaData(bind=self.connectable)

        # Options
        # -------

        # TODO this should be done in the store
        # merge options
        the_options = {}
        the_options.update(store.options)
        the_options.update(options)
        options = the_options

        self.include_summary = options.get("include_summary", True)
        self.include_cell_count = options.get("include_cell_count", True)
        self.safe_labels = options.get("safe_labels", False)
        self.label_counter = 1

        # Whether to ignore cells where at least one aggregate is NULL
        self.exclude_null_agregates = options.get("exclude_null_agregates",
                                                 True)

        # Mapper
        # ------

        # Mapper is responsible for finding corresponding physical columns to
        # dimension attributes and fact measures. It also provides information
        # about relevant joins to be able to retrieve certain attributes.

        if options.get("use_denormalization"):
            mapper_class = DenormalizedMapper
        else:
            mapper_class = SnowflakeMapper

        self.logger.debug("using mapper %s for cube '%s' (locale: %s)" %
                          (str(mapper_class.__name__), cube.name, locale))

        self.mapper = mapper_class(cube, locale=self.locale, **options)
        self.logger.debug("mapper schema: %s" % self.mapper.schema)

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

    def is_builtin_function(self, name, aggregate):
        return self.builtin_function(name, aggregate) is not None

    def set_locale(self, locale):
        """Change the browser's locale"""
        self.logger.debug("changing browser's locale to %s" % locale)
        self.mapper.set_locale(locale)
        self.locale = locale

    def fact(self, key_value, fields=None):
        """Get a single fact with key `key_value` from cube.

        Number of SQL queries: 1."""

        attributes = self.cube.get_attributes(fields)

        builder = QueryBuilder(self)
        builder.denormalized_statement(attributes=attributes,
                                       include_fact_key=True)

        builder.fact(key_value)

        cursor = self.execute_statement(builder.statement, "facts")
        row = cursor.fetchone()

        if row:
            # Convert SQLAlchemy object into a dictionary
            record = dict(zip(builder.labels, row))
        else:
            record = None

        cursor.close()

        return record

    def facts(self, cell=None, fields=None, order=None, page=None,
              page_size=None):
        """Return all facts from `cell`, might be ordered and paginated.

        Number of SQL queries: 1.
        """

        cell = cell or Cell(self.cube)

        attributes = self.cube.get_attributes(fields)

        builder = QueryBuilder(self)
        builder.denormalized_statement(cell,
                                       attributes,
                                       include_fact_key=True)
        builder.paginate(page, page_size)
        order = self.prepare_order(order, is_aggregate=False)
        builder.order(order)

        cursor = self.execute_statement(builder.statement,
                                        "facts")

        return ResultIterator(cursor, builder.labels)

    def test(self, aggregate=False, **options):
        """Tests whether the statement can be constructed."""
        cell = Cell(self.cube)

        attributes = self.cube.all_attributes

        builder = QueryBuilder(self)
        statement = builder.denormalized_statement(cell,
                                                   attributes)
        statement = statement.limit(1)
        result = self.connectable.execute(statement)
        result.close()

        if aggregate:
            result = self.aggregate()

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

        builder = QueryBuilder(self)
        builder.members_statement(cell, attributes)
        builder.paginate(page, page_size)
        builder.order(order)

        result = self.execute_statement(builder.statement, "members")

        return ResultIterator(result, builder.labels)

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

        builder = QueryBuilder(self)
        builder.denormalized_statement(cell,
                                       attributes,
                                       include_fact_key=True)
        builder.paginate(0, 1)
        cursor = self.execute_statement(builder.statement,
                                        "path details")

        row = cursor.fetchone()

        if row:
            member = dict(zip(builder.labels, row))
        else:
            member = None

        return member

    def execute_statement(self, statement, label=None):
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

        result = AggregationResult(cell=cell, aggregates=aggregates)

        # Summary
        # -------

        if self.include_summary or not (drilldown or split):

            builder = QueryBuilder(self)
            builder.aggregation_statement(cell,
                                          aggregates=aggregates,
                                          drilldown=drilldown,
                                          summary_only=True)

            cursor = self.execute_statement(builder.statement,
                                            "aggregation summary")
            row = cursor.fetchone()

            # TODO: use builder.labels
            if row:
                # Convert SQLAlchemy object into a dictionary
                record = dict(zip(builder.labels, row))
            else:
                record = None

            cursor.close()
            result.summary = record


        # Drill-down
        # ----------
        #
        # Note that a split cell if present prepends the drilldown

        if drilldown or split:
            if not (page_size and page is not None):
                self.assert_low_cardinality(cell, drilldown)

            result.levels = drilldown.result_levels(include_split=bool(split))

            self.logger.debug("preparing drilldown statement")

            builder = QueryBuilder(self)
            builder.aggregation_statement(cell,
                                          drilldown=drilldown,
                                          aggregates=aggregates,
                                          split=split)
            builder.paginate(page, page_size)
            builder.order(order)

            cursor = self.execute_statement(builder.statement,
                                            "aggregation drilldown")

            #
            # Find post-aggregation calculations and decorate the result
            #
            result.calculators = calculators_for_aggregates(self.cube,
                                                            aggregates,
                                                            drilldown,
                                                            split,
                                                            available_aggregate_functions())
            result.cells = ResultIterator(cursor, builder.labels)
            result.labels = builder.labels

            # TODO: Introduce option to disable this

            if self.include_cell_count:
                count_statement = builder.statement.alias().count()
                row_count = self.execute_statement(count_statement).fetchone()
                total_cell_count = row_count[0]
                result.total_cell_count = total_cell_count

        elif result.summary is not None:
            # Do calculated measures on summary if no drilldown or split
            # TODO: should not we do this anyway regardless of
            # drilldown/split?
            calculators = calculators_for_aggregates(self.cube,
                                                     aggregates,
                                                    drilldown,
                                                    split,
                                                    available_aggregate_functions())
            for calc in calculators:
                calc(result.summary)

        # If exclude_null_aggregates is True then don't include cells where
        # at least one of the bult-in aggregates is NULL
        if result.cells is not None and self.exclude_null_agregates:
            afuncs = available_aggregate_functions()
            aggregates = [agg for agg in aggregates if not agg.function or agg.function in afuncs]
            names = [str(agg) for agg in aggregates]
            result.exclude_if_null = names

        return result

    def builtin_function(self, name, aggregate):
        """Returns a built-in function for `aggregate`"""
        try:
            function = get_aggregate_function(name)
        except KeyError:
            if name and not name in available_calculators():
                raise ArgumentError("Unknown aggregate function %s "
                                    "for aggregate %s" % \
                                    (name, str(aggregate)))
            else:
                # The function is post-aggregation calculation
                return None

        return function

    def _log_statement(self, statement, label=None):
        label = "SQL(%s):" % label if label else "SQL:"
        self.logger.debug("%s\n%s\n" % (label, str(statement)))

    def validate(self):
        """Validate physical representation of model. Returns a list of
        dictionaries with keys: ``type``, ``issue``, ``object``.

        Types might be: ``join`` or ``attribute``.

        The ``join`` issues are:

        * ``no_table`` - there is no table for join
        * ``duplicity`` - either table or alias is specified more than once

        The ``attribute`` issues are:

        * ``no_table`` - there is no table for attribute
        * ``no_column`` - there is no column for attribute
        * ``duplicity`` - attribute is found more than once

        """
        issues = []

        # Check joins

        tables = set()
        aliases = set()
        alias_map = {}
        #
        for join in self.mapper.joins:
            self.logger.debug("join: %s" % (join, ))

            if not join.master.column:
                issues.append(("join", "master column not specified", join))
            if not join.detail.table:
                issues.append(("join", "detail table not specified", join))
            elif join.detail.table == self.mapper.fact_name:
                issues.append(("join", "detail table should not be fact table", join))

            master_table = (join.master.schema, join.master.table)
            tables.add(master_table)

            detail_alias = (join.detail.schema, join.alias or join.detail.table)

            if detail_alias in aliases:
                issues.append(("join", "duplicate detail table %s" % detail_table, join))
            else:
                aliases.add(detail_alias)

            detail_table = (join.detail.schema, join.detail.table)
            alias_map[detail_alias] = detail_table

            if detail_table in tables and not join.alias:
                issues.append(("join", "duplicate detail table %s (no alias specified)" % detail_table, join))
            else:
                tables.add(detail_table)

        # Check for existence of joined tables:
        physical_tables = {}

        # Add fact table to support simple attributes
        physical_tables[(self.fact_table.schema, self.fact_table.name)] = self.fact_table
        for table in tables:
            try:
                physical_table = sqlalchemy.Table(table[1], self.metadata,
                                        autoload=True,
                                        schema=table[0] or self.mapper.schema)
                physical_tables[(table[0] or self.mapper.schema, table[1])] = physical_table
            except sqlalchemy.exc.NoSuchTableError:
                issues.append(("join", "table %s.%s does not exist" % table, join))

        # check attributes

        attributes = self.mapper.all_attributes()
        physical = self.mapper.map_attributes(attributes)

        for attr, ref in zip(attributes, physical):
            alias_ref = (ref.schema, ref.table)
            table_ref = alias_map.get(alias_ref, alias_ref)
            table = physical_tables.get(table_ref)

            if table is None:
                issues.append(("attribute", "table %s.%s does not exist for attribute %s" % (table_ref[0], table_ref[1], self.mapper.logical(attr)), attr))
            else:
                try:
                    c = table.c[ref.column]
                except KeyError:
                    issues.append(("attribute", "column %s.%s.%s does not exist for attribute %s" % (table_ref[0], table_ref[1], ref.column, self.mapper.logical(attr)), attr))

        return issues


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
                    and any(cell[agg] is None for agg in self.exclude_if_nul):
                continue

            yield dict(zip(self.labels, row))
