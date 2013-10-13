# -*- coding=utf -*-
# Actually, this is a furry snowflake, not a nice star

from ...browser import *
from ...common import get_logger
from ...statutils import calculators_for_aggregates, available_calculators
from ...errors import *
from .mapper import SnowflakeMapper, DenormalizedMapper
from .functions import get_aggregate_function, available_aggregate_functions
from .query import QueryBuilder

import collections
import re
import datetime

try:
    import sqlalchemy
    import sqlalchemy.sql as sql

except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")

__all__ = [
    "SnowflakeBrowser",
    "SnapshotBrowser"
]

_EXPR_EVAL_NS = {
    "sqlalchemy": sqlalchemy,
    "sql": sql,
    "func": sql.expression.func,
    "case": sql.expression.case,
    "text": sql.expression.text,
    "datetime": datetime,
    "re": re
}


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

    def __init__(self, cube, store, locale=None, metadata=None,
                 debug=False, **options):
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
            "actions": ["aggregate", "members", "fact", "facts", "cell"],
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

        cursor = self.execute_statement(builder.statement,
                                        "facts")
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

    def members(self, cell, dimension, depth=None, hierarchy=None, page=None,
                page_size=None, order=None, **options):
        """Return values for `dimension` with level depth `depth`. If `depth`
        is ``None``, all levels are returned.

        Number of database queries: 1.
        """
        dimension = self.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)

        levels = hierarchy.levels

        if depth == 0:
            raise ArgumentError("Depth for dimension values should not be 0")
        elif depth is not None:
            levels = levels[0:depth]

        # TODO: this might unnecessarily add fact table as well, there might
        #       be cases where we do not want that (hm, might be? really? note
        #       the cell)

        attributes = []
        for level in levels:
            attributes.extend(level.attributes)

        cond = self.condition_for_cell(cell)

        statement = self.denormalized_statement(attributes=attributes,
                                                        include_fact_key=False,
                                                        condition_attributes=
                                                        cond.attributes)
        if cond.condition is not None:
            statement = statement.where(cond.condition)

        statement = self.paginated_statement(statement, page, page_size)
        order_levels = [(dimension, hierarchy, levels)]
        statement = self.ordered_statement(statement, order,
                                                   order_levels)

        group_by = [self.column(attr) for attr in attributes]
        statement = statement.group_by(*group_by)

        if self.debug:
            self.logger.info("dimension members SQL:\n%s" % statement)

        result = self.connectable.execute(statement)
        labels = self.logical_labels(statement.columns)

        return ResultIterator(result, labels)

    def path_details(self, dimension, path, hierarchy=None):
        """Returns details for `path` in `dimension`. Can be used for
        multi-dimensional "breadcrumbs" in a used interface.

        Number of SQL queries: 1.
        """

        statement = self.detail_statement(dimension, path, hierarchy)
        labels = self.logical_labels(statement.columns)

        if self.debug:
            self.logger.info("path details SQL:\n%s" % statement)

        cursor = self.connectable.execute(statement)
        row = cursor.fetchone()

        if row:
            record = dict(zip(labels, row))
        else:
            record = None

        cursor.close()

        return record

    def execute_statement(self, statement, label=None):
        """Execute the `statement`, optionally log it. Returns the result
        cursor."""
        self._log_statement(statement, label)
        return self.connectable.execute(statement)

    def aggregate(self, cell=None, measures=None, drilldown=None, split=None,
                  attributes=None, page=None, page_size=None, order=None,
                  include_summary=None, include_cell_count=None,
                  aggregates=None, **options):
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

        # Preparation
        # -----------

        if not cell:
            cell = Cell(self.cube)

        aggregates = self.prepare_aggregates(aggregates, measures)
        drilldown = Drilldown(drilldown, cell)
        result = AggregationResult(cell=cell, aggregates=aggregates)

        # Summary
        # -------

        if include_summary or \
                (include_summary is None and self.include_summary) or \
                not drilldown:

            builder = QueryBuilder(self)
            builder.aggregation_statement(cell,
                                          aggregates=aggregates)

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

        if include_cell_count is None:
            include_cell_count = self.include_cell_count


        # Drill-down
        # ----------
        #
        # Note that a split cell if present prepends the drilldown

        if drilldown or split:
            if page_size and page is not None:
                self.assert_low_cardinality(cell, drilldown)

            result.levels = drilldown.result_levels(include_split=bool(split))

            self.logger.debug("preparing drilldown statement")

            builder = QueryBuilder(self)
            builder.aggregation_statement(cell,
                                          drilldown=drilldown,
                                          aggregates=aggregates,
                                          split=split)
            builder.paginate(page, page_size)
            order = self.prepare_order(order, is_aggregate=True)
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

            if include_cell_count:
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

        return result

    def aggregation_statement(self, cell, aggregates=None, attributes=None,
                              drilldown=None, split=None):
        """Return a statement for summarized aggregation. `whereclause` is
        same as SQLAlchemy `whereclause` for
        `sqlalchemy.sql.expression.select()`. `attributes` is list of logical
        references to attributes to be selected. If it is ``None`` then all
        attributes are used. `drilldown` has to be a dictionary. Use
        `levels_from_drilldown()` to prepare correct drill-down statement."""

        # 1. collect INNER or LEFT conditions

        deferred_conditions = []
        master_conditions = []
        for condition in conditions:
            if condition.join_method in ("match", "master"):
                master_conditions.append(condition)
            else:
                deffered_conditions.append(condition)

        statement + conditions

        cell_condition = self.condition_for_cell(cell)
        # We have:
        #   condition.attributes
        #   condition.condition
        # We needs:
        #   statement

        for condition in cell_conditions:
            snowflake.append_condition(condition)

        # match and master attributes are joined first

        if split:
            split_condition = self.condition_for_cell(split)
        else:
            split_condition = None

        if attributes:
            raise NotImplementedError("attribute selection is not yet supported")

        # if not attributes:
        #     attributes = set()

        #     if drilldown:
        #         for dditem in drilldown:
        #             for level in dditem.levels:
        #                 attributes |= set(level.attributes)

        attributes = set(attributes) | set(cell_cond.attributes)
        if split_dim_cond:
            attributes |= set(split_dim_cond.attributes)

        # We need condition attributes for this join
        join_product = self.join_expression_for_attributes(attributes)
        join_expression = join_product.expression

        selection = []

        group_by = None

        # Prepare selection and group_by for drilldown
        if split_dim_cond or drilldown:
            group_by = []

            # Prepare split expression for selection and group-by
            if split_dim_cond:
                expr = sql.expression.case([(split_dim_cond.condition, True)],
                                                            else_=False)
                expr = expr.label(SPLIT_DIMENSION_NAME)

                group_by.append(expr)
                selection.append(expr)

            for dditem in drilldown:
                for level in dditem.levels:
                    columns = [self.column(attr) for attr in level.attributes
                                                        if attr in attributes]
                    group_by.extend(columns)
                    selection.extend(columns)

                    # Prepare period-to-date condition
        if not aggregates:
            raise ArgumentError("List of aggregates sohuld not be empty")

        # Collect expressions of aggregate functions
        selection += self.builtin_aggregate_expressions(aggregates,
                                                        coalesce_measures=bool(join_product.outer_details))

        # Drill-down statement
        # --------------------
        #
        select = sql.expression.select(selection,
                                       from_obj=join_expression,
                                       use_labels=True,
                                       group_by=group_by)

        conditions = []
        if cell_cond.condition is not None:
            conditions.append(cell_cond.condition)

        # Add periods-to-date condition
        ptd_condition = self._ptd_condition(cell, drilldown)
        if ptd_condition is not None:
            conditions.append(ptd_condition)

        if conditions:
            select = select.where(sql.expression.and_(*conditions) if
                                  len(conditions) > 1 else conditions[0])

        self._log_statement(select, "aggregate select")

        return select

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

    def detail_statement(self, dimension, path, hierarchy=None):
        """Returns statement for dimension details. `attributes` should be a
        list of attributes from one dimension that is one branch
        (master-detail) of a star/snowflake."""

        dimension = self.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)
        attributes = hierarchy.all_attributes

        product = self.join_expression_for_attributes(attributes,
                                                        include_fact=False)
        expression = product.expression

        columns = self.columns(attributes)
        select = sql.expression.select(columns,
                                       from_obj=expression,
                                       use_labels=True)

        cond = self.condition_for_point(dimension, path, hierarchy)
        select = select.where(cond.condition)

        return select

    def fact_statement(self, key_value):
        """Return a statement for selecting a single fact based on `key_value`"""

        key_column = self.fact_table.c[self.fact_key]

        statement = self.denormalized_statement()
        statement = statement.where(condition)

        return statement

    def _ptd_condition(self, cell, drilldown):
        """Returns "periods to date" condition for cell."""

        # Include every level only once
        levels = set()

        # For the cell:
        if cell:
            levels |= set(item[2] for item in cell.deepest_levels())

        # For drilldown:
        if drilldown:
            levels |= set(item[2] for item in drilldown.deepest_levels())

        # Collect the conditions
        #
        # Conditions are currently specified in the mappings as "condtition"
        #

        # Collect relevant columns – those with conditions
        physicals = []
        for level in levels:
            ref = self.mapper.physical(level.key)
            if ref.condition:
                physicals.append(ref)

        # Construct the conditions from the physical attribute expression
        conditions = []
        for ref in physicals:

            table = self.table(ref.schema, ref.table)
            try:
                column = table.c[ref.column]
            except:
                raise BrowserError("Unknown column '%s' in table '%s'" % (ref.column, ref.table))

            # evaluate the condition expression
            function = eval(compile(ref.condition, '__expr__', 'eval'), _EXPR_EVAL_NS.copy())
            if not callable(function):
                raise BrowserError("Cannot evaluate a callable object from reference's condition expr: %r" % ref)

            condition = function(column)

            conditions.append(condition)

        # TODO: What about invert?
        condition = sql.expression.and_(*conditions)

        return condition

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

        # Check attributes

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

    def __iter__(self):
        return self

    def next(self):
        if not self.batch:
            many = self.result.fetchmany()
            if not many:
                raise StopIteration
            self.batch = collections.deque(many)

        row = self.batch.popleft()

        print "--- row: %s" % (row, )
        return dict(zip(self.labels, row))


class SnapshotBrowser(SnowflakeBrowser):
    def __init__(self, cube, **options):
        super(SnapshotBrowser, self).__init__(cube, **options)

        snap_info = {
            'dimension': 'daily_date',
            'level_attribute': 'daily_datetime',
            'aggregation': 'max'
        }

        snap_info.update(cube.info.get('snapshot', {}))
        self.snapshot_dimension = cube.dimension(snap_info['dimension'])
        self.snapshot_level_attrname = snap_info['level_attribute']
        self.snapshot_aggregation = snap_info['aggregation']

    def snapshot_level_attribute(self, drilldown):
        if drilldown:
            for dditem in drilldown:
                if dditem.dimension.name == self.snapshot_dimension.name:
                    if len(dditem.hierarchy.levels) > len(dditem.levels):
                        return self.snapshot_dimension.attribute(self.snapshot_level_attrname), False
                    elif len(dditem.hierarchy.levels) == len(dditem.levels):
                        if len(dditem.levels) == 1 and dditem.levels[0].name == 'dow':
                            return self.snapshot_dimension.attribute(self.snapshot_level_attrname), False
                        else:
                            return None, False

        return self.snapshot_dimension.attribute(self.snapshot_level_attrname), True

    def aggregation_statement(self, cell, aggregates=None, attributes=None,
                              drilldown=None, split=None):
        """Prototype of 'snapshot cube' aggregation style."""

        cell_cond = self.condition_for_cell(cell)

        if split:
            split_dim_cond = self.condition_for_cell(split)
        else:
            split_dim_cond = None

        if not attributes:
            attributes = set()

            if drilldown:
                for dditem in drilldown:
                    for level in dditem.levels:
                        attributes |= set(level.attributes)

        attributes = set(attributes) | set(cell_cond.attributes)
        if split_dim_cond:
            attributes |= set(split_dim_cond.attributes)

        join_product = self.join_expression_for_attributes(attributes)
        join_expression = join_product.expression

        selection = []

        group_by = None

        if split_dim_cond or drilldown:
            group_by = []

            if split_dim_cond:
                group_by.append(sql.expression.case([(split_dim_cond.condition, True)], else_=False).label(SPLIT_DIMENSION_NAME))
                selection.append(sql.expression.case([(split_dim_cond.condition, True)], else_=False).label(SPLIT_DIMENSION_NAME))

            for dditem in drilldown:
                for level in dditem.levels:
                    columns = [self.column(attr) for attr in level.attributes
                               if attr in attributes]
                    group_by.extend(columns)
                    selection.extend(columns)

        conditions = []
        if cell_cond.condition is not None:
            conditions.append(cell_cond.condition)

        # Add periods-to-date condition
        ptd_condition = self._ptd_condition(cell, drilldown)
        if ptd_condition is not None:
            conditions.append(ptd_condition)

        # We must produce, under certain conditions, a subquery:
        #   - If the drilldown contains the date dimension, but not a full path for the given hierarchy. OR
        #   - If the drilldown contains the date dimension, and it's a full path for the given hierarchy,
        #     but the hierarchy contains only 'dow'. OR
        #   - If the drilldown does not contain the date dimension.
        #
        # We create a select() with special alias 'snapshot_browser_subquery', using the joins, conditions, and group_by
        # of the main query. We append to the select columns not the measure aggregations, but instead the min() or max()
        # of the specified dimension level attribute. Then we add the subquery to join_expression with a join clause of the existing
        # drilldown levels, plus dim.lowest_level == snapshot_browser_subquery.snapshot_level.

        snapshot_level_attribute, needs_join_added = self.snapshot_level_attribute(drilldown)

        outer_detail_join = False
        if snapshot_level_attribute:
            if needs_join_added:
                # TODO: check if this works with product.outer_detail = True
                product = self.join_expression_for_attributes(attributes | set([snapshot_level_attribute]))
                join_expression = product.expression
                outer_detail_join = bool(product.outer_details)

            subq_join_expression = join_expression
            subq_selection = [ s.label('col%d' % i) for i, s in enumerate(selection) ]
            subq_group_by = group_by[:] if group_by else None
            subq_conditions = conditions[:]

            level_expr = getattr(sql.expression.func, self.snapshot_aggregation)(self.column(snapshot_level_attribute)).label('the_snapshot_level')
            subq_selection.append(level_expr)
            subquery = sql.expression.select(subq_selection, from_obj=subq_join_expression, use_labels=True, group_by=subq_group_by)

            if subq_conditions:
                subquery = subquery.where(sql.expression.and_(*subq_conditions) if len(subq_conditions) > 1 else subq_conditions[0])

            # Prepare the snapshot subquery
            subquery = subquery.alias('the_snapshot_subquery')
            subq_joins = []

            cols = []
            for i, s in enumerate(subq_selection[:-1]):
                col = sql.expression.literal_column("%s.col%d" %
                                                    (subquery.name, i))
                cols.append(col)

            for left, right in zip(selection, cols):
                subq_joins.append(left == right)

            subq_joins.append(self.column(snapshot_level_attribute) == sql.expression.literal_column("%s.%s" % (subquery.name, 'the_snapshot_level')))
            join_expression = join_expression.join(subquery, sql.expression.and_(*subq_joins))

        if not aggregates:
            raise ArgumentError("List of aggregates sohuld not be empty")

        # Collect "columns" for measure aggregations
        selection += self.builtin_aggregate_expressions(aggregates,
                                                        coalesce_measures=outer_detail_join)

        select = sql.expression.select(selection,
                                       from_obj=join_expression,
                                       use_labels=True,
                                       group_by=group_by)

        if conditions:
            select = select.where(sql.expression.and_(*conditions) if
                                  len(conditions) > 1 else conditions[0])

        return select
