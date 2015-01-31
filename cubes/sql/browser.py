# -*- encoding=utf -*-
# Actually, this is a furry snowflake, not a nice star

from __future__ import absolute_import

from ..browser import AggregationBrowser, AggregationResult, Drilldown
from ..browser import PointCut, RangeCut, SetCut
from ..logging import get_logger
from ..statutils import calculators_for_aggregates, available_calculators
from ..errors import *
from ..stores import Store
from .mapper import SnowflakeMapper, DenormalizedMapper
from .functions import get_aggregate_function, available_aggregate_functions
from .query import QueryBuilder
from ..model import base_attributes
from .schema import StarSchema, to_join
from .utils import paginate_query, order_query

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


def star_schema_from_cube(cube, metadata, mapper, tables=None):
    """Creates a :class:`StarSchema` instance for `cube` within database
    environment specified by `metadata` using logical to physical `mapper`."""
    # TODO: remove requirement for the mapper, use mapping options and create
    # mapper here

    names = [attr.name for attr in cube.all_attributes]
    mappings = {attr:mapper.physical(attr) for attr in names}

    star = StarSchema(cube.name,
                      metadata,
                      mappings=mappings,
                      fact=mapper.fact_name,
                      joins=cube.joins,
                      tables=tables,
                      schema=mapper.schema
                      )
    return star

def get_natural_order(attributes):
    """Return natural order dictionary for `attributes`"""
    return {str(attr): attr.order for attr in attributes}

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

    def __init__(self, cube, store, locale=None, debug=False, **kwargs):
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
        super(SnowflakeBrowser, self).__init__(cube, store)

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
        # TODO this should be done in the store
        options = {}
        options.update(store.options)
        options.update(kwargs)

        # TODO: REFACTORING: make sure these options are used
        self.include_summary = options.get("include_summary", True)
        self.include_cell_count = options.get("include_cell_count", True)
        self.safe_labels = options.get("safe_labels", False)
        self.label_counter = 1

        # Whether to ignore cells where at least one aggregate is NULL
        # TODO: this is undocumented
        self.exclude_null_agregates = options.get("exclude_null_agregates",
                                                 True)

        # Mapper
        # ------

        # Mapper is responsible for finding corresponding physical columns to
        # dimension attributes and fact measures. It also provides information
        # about relevant joins to be able to retrieve certain attributes.

        # FIXME: mapper sohuld be a cube-free object with preconfigured naming
        # conventions and should be provided by the store.
        # TODO: change this to is_denormalized
        if options.get("use_denormalization"):
            mapper_class = DenormalizedMapper
        else:
            mapper_class = SnowflakeMapper

        self.logger.debug("using mapper %s for cube '%s' (locale: %s)" %
                          (str(mapper_class.__name__), cube.name, locale))

        # We need mapper just to construct metadata for the star
        mapper = mapper_class(cube, locale=self.locale, **options)

        # TODO: whis should include also aggregates if the underlying table is
        # already pre-aggregated
        base = base_attributes(cube.all_attributes)
        mappings = {attr.name:mapper.physical(attr) for attr in base}

        # TODO: include table expressions
        # TODO: I have a feeling that creation of this should belong to the
        # store
        tables = options.get("tables")

        if cube.joins:
            joins = [to_join(join) for join in cube.joins]
        else:
            joins = []

        self.star = StarSchema(self.cube.name,
                               metadata,
                               mappings=mappings,
                               fact=mapper.fact_name,
                               joins=joins,
                               schema=mapper.schema,
                               tables=tables)
        # Create a dictionary attribute -> column to be used in aggregate
        # functions
        # TODO: add __fact_key__
        self.base_columns = {attr.name:self.star.column(attr.name)
                                for attr in base}

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

    # TODO: requires rewrite
    def fact(self, key_value, fields=None):
        """Get a single fact with key `key_value` from cube.

        Number of SQL queries: 1."""

        # TODO: safe labels 
        core = star.denormalized_statement(fields,
                                           include_fact_key=True)

        core = core.where(core.c[self.fact_key] == key_value)

        cursor = self.execute(core, "facts")
        row = cursor.fetchone()

        if row:
            # Convert SQLAlchemy object into a dictionary
            record = dict(zip(builder.labels, row))
        else:
            record = None

        cursor.close()

        return record

    # TODO: requires rewrite
    def facts(self, cell=None, fields=None, order=None, page=None,
              page_size=None):
        """Return all facts from `cell`, might be ordered and paginated.

        Number of SQL queries: 1.
        """
        raise NotImplementedError("Queued for refactoring")

        cell = cell or Cell(self.cube)

        attributes = self.cube.get_attributes(fields)

        builder = QueryBuilder(self)
        builder.denormalized_statement(cell,
                                       attributes,
                                       include_fact_key=True)
        builder.paginate(page, page_size)
        order = self.prepare_order(order, is_aggregate=False)
        builder.order(order)

        cursor = self.execute(builder.statement,
                                        "facts")

        return ResultIterator(cursor, builder.labels)

    # TODO: requires rewrite
    def test(self, aggregate=False, **options):
        """Tests whether the statement can be constructed."""
        raise NotImplementedError("Queued for refactoring")
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

    # TODO: requires rewrite
    def provide_members(self, cell, dimension, depth=None, hierarchy=None,
                        levels=None, attributes=None, page=None,
                        page_size=None, order=None):
        """Return values for `dimension` with level depth `depth`. If `depth`
        is ``None``, all levels are returned.

        Number of database queries: 1.
        """
        raise NotImplementedError("Queued for refactoring")
        if not attributes:
            attributes = []
            for level in levels:
                attributes += level.attributes

        builder = QueryBuilder(self)
        builder.members_statement(cell, attributes)
        builder.paginate(page, page_size)
        builder.order(order)

        result = self.execute(builder.statement, "members")

        return ResultIterator(result, builder.labels)

    # TODO: requires rewrite
    def path_details(self, dimension, path, hierarchy=None):
        """Returns details for `path` in `dimension`. Can be used for
        multi-dimensional "breadcrumbs" in a used interface.

        Number of SQL queries: 1.
        """
        raise NotImplementedError("Queued for refactoring")
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
        cursor = self.execute(builder.statement,
                                        "path details")

        row = cursor.fetchone()

        if row:
            member = dict(zip(builder.labels, row))
        else:
            member = None

        return member

    def execute(self, statement, label=None):
        """Execute the `statement`, optionally log it. Returns the result
        cursor."""
        self._log_statement(statement, label)
        return self.connectable.execute(statement)

    def is_builtin_function(self, function_name, aggregate):
        # FIXME: return actual truth
        return True

    # TODO: requires rewrite
    def provide_aggregate(self, cell, aggregates, drilldown, split, order,
                          page, page_size, across=None, **options):
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

        # TODO: implement drill-across
        if across:
            raise NotImplementedError("Drill-across is not yet implemented")

        result = AggregationResult(cell=cell, aggregates=aggregates)

        # TODO: remove unnecessary parts of the following discussion once
        # implemented and documented

        # Discussion:
        # -----------
        # the only diference between the summary statement and non-summary
        # statement is the inclusion of the group-by clause

        # Summary
        # -------

        if self.include_summary or not (drilldown or split):
            statement = self.aggregation_statement(cell,
                                                   aggregates=aggregates,
                                                   drilldown=drilldown,
                                                   for_summary=True)

            cursor = self.execute(statement, "aggregation summary")
            row = cursor.fetchone()

            # TODO: use builder.labels
            if row:
                # Convert SQLAlchemy object into a dictionary
                labels = [col.name for col in statement.columns]
                record = dict(zip(labels, row))
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

            natural_order = drilldown.natural_order
            # TODO: add natural order of aggregates

            self.logger.debug("preparing drilldown statement")

            statement = self.aggregation_statement(cell,
                                                   aggregates=aggregates,
                                                   drilldown=drilldown)
            # TODO: look the order_query spec for arguments
            # TODO: use safe labels too
            statement = paginate_query(statement, page, page_size)
            statement = order_query(statement,
                                    order,
                                    natural_order,
                                    labels=None)

            cursor = self.execute(statement, "aggregation drilldown")

            #
            # Find post-aggregation calculations and decorate the result
            #
            result.calculators = calculators_for_aggregates(self.cube,
                                                            aggregates,
                                                            drilldown,
                                                            split,
                                                            available_aggregate_functions())
            # TODO: safe labels
            labels = [col.name for col in statement.columns]
            result.cells = ResultIterator(cursor, labels)
            result.labels = labels

            # TODO: Introduce option to disable this

            if self.include_cell_count:
                # TODO: we want to get unpaginated number of records here
                count_statement = statement.alias().count()
                row_count = self.execute(count_statement).fetchone()
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

    def aggregation_statement(self, cell, aggregates, drilldown=None,
                              split=None, attributes=None, for_summary=False,
                              across=None):
        """Builds a statement to aggregate the `cell`.

        * `cell` – `Cell` to aggregate
        * `aggregates` – list of aggregates to consider (should not be empty)
        * `drilldown` – an optional `Drilldown` object
        * `split` – split cell for split condition
        * `for_summary` – do not perform `GROUP BY` for the drilldown. The
          drilldown is used only for choosing tables to join
        * `across` – cubes that share dimensions
        """
        # TODO: `across` should be used here
        # TODO: PTD
        # TODO: semiadditive

        if across:
            raise NotImplementedError("Drill-across is not yet implemented")

        if not aggregates:
            raise ArgumentError("List of aggregates sohuld not be empty")

        drilldown = drilldown or Drilldown()

        self.logger.debug("prepare aggregation statement. cell: '%s' "
                          "drilldown: '%s' for summary: %s" %
                          (",".join([str(cut) for cut in cell.cuts]),
                          drilldown, for_summary))

        select_attributes = drilldown.all_attributes
        all_attributes = cell.key_attributes
        all_attributes += select_attributes

        if split:
            all_attributes += split.all_attributes

        # JOIN
        # ----

        base = base_attributes(all_attributes)
        star = self.star.star(base)

        # Drilldown – Group-by
        # --------------------
        #
        # SELECT – Prepare the master selection
        #     * master drilldown items

        selection = [self.attribute_column(a) for a in set(drilldown.all_attributes)]

        # SPLIT
        # -----
        if split:
            split_column = self._split_cell_column(split)
            selection.append(split_column)

        # WHERE
        # -----
        conditions = self.conditions_for_cuts(cell.cuts)
        condition = sql.expression.and_(*conditions)

        group_by = selection[:] if not for_summary else None

        # TODO: insert semiadditives here
        aggregate_cols = [self.aggregate_column(aggr) for aggr in aggregates]

        if for_summary:
            # Don't include the group-by part (see issue #157 for more
            # information)
            selection = aggregate_cols
        else:
            selection += aggregate_cols

        statement = sql.expression.select(selection,
                                          from_obj=star,
                                          use_labels=True,
                                          whereclause=condition,
                                          group_by=group_by)

        return statement

    def conditions_for_cuts(self, cuts):
        """Constructs conditions for all cuts in the `cell`. Returns a list of
        SQL conditional expressions.
        """

        conditions = []

        for cut in cuts:
            dim = self.cube.dimension(cut.dimension)

            if isinstance(cut, PointCut):
                path = cut.path
                condition = self.condition_for_point(dim, path, cut.hierarchy,
                                                     cut.invert)

            elif isinstance(cut, SetCut):
                set_conds = []

                for path in cut.paths:
                    condition = self.condition_for_point(dim, path,
                                                         cut.hierarchy,
                                                         invert=False)
                    set_conds.append(condition)

                condition = sql.expression.or_(*set_conds)

                if cut.invert:
                    condition = sql.expression.not_(condition)

            elif isinstance(cut, RangeCut):
                condition = self.range_condition(cut.dimension,
                                                 cut.hierarchy,
                                                 cut.from_path,
                                                 cut.to_path, cut.invert)

            else:
                raise ArgumentError("Unknown cut type %s" % type(cut))

            conditions.append(condition)

        return conditions

    def condition_for_point(self, dim, path, hierarchy=None, invert=False):
        """Returns a `Condition` tuple (`attributes`, `conditions`,
        `group_by`) dimension `dim` point at `path`. It is a compound
        condition - one equality condition for each path element in form:
        ``level[i].key = path[i]``"""

        conditions = []

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise ArgumentError("Path has more items (%d: %s) than there are levels (%d) "
                                "in dimension %s" % (len(path), path, len(levels), dim.name))

        for level, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.attribute_column(level.key)
            conditions.append(column == value)

        condition = sql.expression.and_(*conditions)

        if invert:
            condition = sql.expression.not_(condition)

        return condition

    def range_condition(self, dim, hierarchy, from_path, to_path, invert=False):
        """Return a condition for a hierarchical range (`from_path`,
        `to_path`). Return value is a `Condition` tuple."""

        dim = self.cube.dimension(dim)

        lower = self._boundary_condition(dim, hierarchy, from_path, 0)
        upper = self._boundary_condition(dim, hierarchy, to_path, 1)

        conditions = []
        if lower is not None:
            conditions.append(lower)
        if upper is not None:
            conditions.append(upper)

        condition = sql.expression.and_(*conditions)

        if invert:
            condition = sql.expression.not_(condition)

        return condition

    def _boundary_condition(self, dim, hierarchy, path, bound, first=True):
        """Return a `Condition` tuple for a boundary condition. If `bound` is
        1 then path is considered to be upper bound (operators < and <= are
        used), otherwise path is considered as lower bound (operators > and >=
        are used )"""

        if not path:
            return None

        last = self._boundary_condition(dim, hierarchy,
                                        path[:-1],
                                        bound,
                                        first=False)

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise ArgumentError("Path has more items (%d: %s) than there are levels (%d) "
                                "in dimension %s" % (len(path), path, len(levels), dim.name))

        conditions = []

        for level, value in zip(levels[:-1], path[:-1]):
            column = self.attribute_column(level.key)
            conditions.append(column == value)

        # Select required operator according to bound
        # 0 - lower bound
        # 1 - upper bound
        if bound == 1:
            # 1 - upper bound (that is <= and < operator)
            operator = sql.operators.le if first else sql.operators.lt
        else:
            # else - lower bound (that is >= and > operator)
            operator = sql.operators.ge if first else sql.operators.gt

        column = self.attribute_column(levels[-1].key)
        conditions.append(operator(column, path[-1]))
        condition = sql.expression.and_(*conditions)

        if last is not None:
            condition = sql.expression.or_(condition, last)

        return condition

    def attribute_column(self, attribute):
        """Return a column expression for a measure, dimension attribute or
        other detail attribute object `attribute`"""
        if not attribute.expression:
            # We assume attribute to be a base attribute
            return self.star.column(str(attribute))

        raise NotImplementedError("Expressions are not yet implemented")

    def aggregate_column(self, aggregate, coalesce_measure=False):
        """Returns an expression that performs the aggregation of attribute
        `aggregate`. The result's label is the aggregate's name.  `aggregate`
        has to be `MeasureAggregate` instance.

        If aggregate function is post-aggregation calculation, then `None` is
        returned.

        Aggregation function names are case in-sensitive.

        If `coalesce_measure` is `True` then selected measure column is wrapped
        in ``COALESCE(column, 0)``.
        """
        # TODO: support aggregate.expression

        if not (aggregate.expression or aggregate.function):
            raise ModelError("Neither expression nor function specified for "
                             "aggregate {} in cube {}"
                             .format(aggregate, self.cube.name))

        if aggregate.expression:
            raise NotImplementedError("Expressions are not yet implemented")

        function_name = aggregate.function.lower()
        function = get_aggregate_function(function_name)

        if not function:
            raise NotImplementedError("I don't know what to do")
            # Original statement:
            return None

        # TODO: this below for FactCountFucntion
        # context = dict(self.base_columns)
        # context["__fact_key__"] = self.attribute_column(self.fact_key)
        expression = function(aggregate, self.base_columns, coalesce_measure)

        return expression

    def _log_statement(self, statement, label=None):
        label = "SQL(%s):" % label if label else "SQL:"
        self.logger.debug("%s\n%s\n" % (label, str(statement)))

    # TODO: needs review
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
