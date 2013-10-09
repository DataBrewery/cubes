# -*- coding=utf -*-
# Actually, this is a furry snowflake, not a nice star

from ...browser import *
from ...common import get_logger
from ...statutils import calculators_for_aggregates, available_calculators
from ...errors import *
from .mapper import SnowflakeMapper, DenormalizedMapper
from .mapper import DEFAULT_KEY_FIELD
from .functions import get_aggregate_function, available_aggregate_functions

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

    def fact(self, key_value):
        """Get a single fact with key `key_value` from cube.

        Number of SQL queries: 1."""

        select = self.fact_statement(key_value)

        if self.debug:
            self.logger.info("fact SQL:\n%s" % select)

        cursor = self.connectable.execute(select)
        row = cursor.fetchone()

        labels = self.logical_labels(select.columns)

        if row:
            # Convert SQLAlchemy object into a dictionary
            record = dict(zip(labels, row))
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

        if not fields:
            attributes = self.cube.all_attributes
            self.logger.debug("facts: getting all fields: %s" % ([a.ref() for a in attributes], ))
        else:
            attributes = self.cube.get_attributes(fields)
            self.logger.debug("facts: getting fields: %s" % fields)

        cond = self.condition_for_cell(cell)
        statement = self.denormalized_statement(attributes=attributes,
                                                        include_fact_key=True,
                                                        condition_attributes=cond.attributes)

        if cond.condition is not None:
            statement = statement.where(cond.condition)

        statement = self.paginated_statement(statement, page, page_size)

        # FIXME: use level based ordering here. What levels to consider? In
        # what order?
        statement = self.ordered_statement(statement, order)

        if self.debug:
            self.logger.info("facts SQL:\n%s" % statement)

        result = self.connectable.execute(statement)
        labels = self.logical_labels(statement.columns)

        return ResultIterator(result, labels)

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

            builder = StatementBuilder(self)
            builder.aggregation_statement(cell, aggregates=aggregates)

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

            builder = StatementBuilder(self)
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

    def denormalized_statement(self, attributes=None, expand_locales=False,
                               include_fact_key=True,
                               condition_attributes=None):
        """Return a statement (see class description for more information) for
        denormalized view. `whereclause` is same as SQLAlchemy `whereclause`
        for `sqlalchemy.sql.expression.select()`. `attributes` is list of
        logical references to attributes to be selected. If it is ``None``
        then all attributes are used. `condition_attributes` contains list of
        attributes that are not going to be selected, but are required for
        WHERE condition.

        Set `expand_locales` to ``True`` to expand all localized attributes.
        """

        if attributes is None:
            attributes = self.mapper.all_attributes()

        if condition_attributes:
            join_attributes = set(attributes) | condition_attributes
        else:
            join_attributes = set(attributes)

        join_product = self.join_expression_for_attributes(join_attributes,
                                                expand_locales=expand_locales)
        join_expression = join_product.expression

        columns = self.columns(attributes, expand_locales=expand_locales)

        if include_fact_key:
            key_column = self.fact_table.c[self.fact_key].label(self.fact_key)
            columns.insert(0, key_column)

        select = sql.expression.select(columns,
                                       from_obj=join_expression,
                                       use_labels=True)

        return select

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
        condition = key_column == key_value

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

    def columns(self, attributes, expand_locales=False):
        """Returns list of columns.If `expand_locales` is True, then one
        column per attribute locale is added."""

        if expand_locales:
            columns = []
            for attr in attributes:
                if attr.is_localizable():
                    columns += [self.column(attr, locale) for locale in attr.locales]
                else: # if not attr.locales
                    columns.append(self.column(attr))
        else:
            columns = [self.column(attr) for attr in attributes]

        return columns

    def _log_statement(self, statement, label=None):
        label = "SQL(%s):" % label if label else "SQL:"
        self.logger.debug("%s\n%s" % (label, str(statement)))

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


# TODO: broken
SnowflakeAttribute = collections.namedtuple("SnowflakeAttribute",
                                            ["attribute", "join"])
"""Aliased table information"""
SnowflakeTable = collections.namedtuple("SnowflakeTable",
                                        ["schema", "table", "alias", "join"])


class SnowflakeSchema(object):
    def __init__(self, cube, mapper, metadata, safe_labels):
        self.cube = cube
        self.mapper = mapper
        self.metadata = metadata
        self.safe_labels = safe_labels

        # Initialize the shema information: tables, column maps, ...
        # TODO check if this is used somewhere
        self.schema = self.mapper.schema

        # Prepare physical fact table - fetch from metadata
        #
        self.fact_key = self.cube.key or DEFAULT_KEY_FIELD
        self.fact_name = self.mapper.fact_name

        try:
            self.fact_table = sqlalchemy.Table(self.fact_name,
                                               self.metadata,
                                               autoload=True,
                                               schema=self.schema)
        except sqlalchemy.exc.NoSuchTableError:
            in_schema = (" in schema '%s'" % self.schema) if self.schema else ""
            msg = "No such fact table '%s'%s." % (self.fact_name, in_schema)
            raise WorkspaceError(msg)

        self.tables = {
                    (self.schema, self.fact_name): self.fact_table
                }

        # Collect all tables and their aliases.
        #
        # table_aliases contains mapping between aliased table name and real
        # table name with alias:
        #
        #       (schema, aliased_name) --> (schema, real_name, alias)
        #
        self.table_aliases = {
            (self.schema, self.fact_name): SnowflakeTable(self.schema,
                                                          self.fact_name,
                                                          None,
                                                          None)
        }

        # Mapping where keys are attributes and values are columns
        self.logical_to_column = {}
        # Mapping where keys are column labels and values are attributes
        self.column_to_logical = {}

        # Collect tables from joins

        for join in self.mapper.joins:
            # just ask for the table
            table = SnowflakeTable(join.detail.schema,
                                   join.detail.table,
                                   join.alias,
                                   join)
            table_alias = (join.detail.schema, join.alias or join.detail.table)
            self.table_aliases[table_alias] = table

    def join_expression(self, attributes, include_fact=True, fact=None):
        """Create partial expression on a fact table with `joins` that can be
        used as core for a SELECT statement. `join` is a list of joins
        returned from mapper (most probably by `Mapper.relevant_joins()`)

        Returns a tuple with attributes: `expression` with a SQLAlchemy
        expression object, and a flag `outer_detail` which is set to `True` if at
        least one join was done using ``detail`` method (RIGHT OUTER JOIN).

        If `include_fact` is ``True`` (default) then fact table is considered
        as starting point. If it is ``False`` The first detail table is
        considered as starting point for joins. This might be useful when
        getting values of a dimension without cell restrictions.

        **Requirement:** joins should be ordered from the "tentacles" towards
        the center of the star/snowflake schema.

        **Algorithm:**

        * FOR ALL JOINS:
          1. get a join (order does not matter)
          2. get master and detail TABLES (raw, not joined)
          3. prepare the join condition on columns from the tables
          4. find join PRODUCTS based on the table keys (schema, table)
          5. perform join on the master/detail PRODUCTS:
             * match: left inner join
             * master: left outer join
             * detail: right outer join – swap master and detail tables and
                       do the left outer join
          6. remove the detail PRODUCT
          7. replace the master PRODUCT with the new one

        * IF there is more than one join product left then some joins are
          missing
        * Result: join products should contain only one item which is the
          final product of the joins
        """

        joins = self.mapper.relevant_joins(attributes)

        # Dictionary of raw tables and their joined products
        joined_products = {}

        if include_fact:
            key = (self.schema, self.fact_name)
            joined_products[key] = fact or self.fact_table

        # Collect all the tables first:
        for join in joins:
            if not join.detail.table or (join.detail.table == self.fact_name and not join.alias):
                raise MappingError("Detail table name should be present and "
                                   "should not be a fact table unless aliased.")

            # Add master table to the list
            table = self.table(join.master.schema, join.master.table)
            joined_products[(join.master.schema, join.master.table)] = table

            # Add (aliased) detail table to the rist
            table = self.table(join.detail.schema, join.alias or join.detail.table)
            key = (join.detail.schema, join.alias or join.detail.table)
            joined_products[key] = table

        # product_list = ["%s: %s" % item for item in joined_products.items()]
        # product_list = "\n".join(product_list)
        # self.logger.debug("products:\n%s" % product_list)

        # Perform the joins
        # =================
        #
        outer_details = []

        for join in joins:
            # Prepare the table keys:
            # Key is a tuple of (schema, table) and is used to get a joined
            # product object
            master = join.master
            master_key = (master.schema, master.table)
            detail = join.detail
            detail_key = (detail.schema, join.alias or detail.table)

            # We need plain tables to get columns for prepare the join
            # condition
            master_table = self.table(join.master.schema, join.master.table)
            detail_table = self.table(join.detail.schema, join.alias or join.detail.table)

            try:
                master_column = master_table.c[master.column]
            except KeyError:
                # self.logger.error("No master column '%s'. Available: %s" % \
                #                    (master.column, str(master_table.columns)))
                raise ModelError('Unable to find master key (schema %s) "%s"."%s" ' \
                                    % join.master[0:3])
            try:
                detail_column = detail_table.c[detail.column]
            except KeyError:
                raise ErrorMappingError('Unable to find detail key (schema %s) "%s"."%s" ' \
                                    % join.detail[0:3])

            # The join condition:
            onclause = master_column == detail_column

            # Get the joined products – might be plain tables or already
            # joined tables
            master_table = joined_products[master_key]
            detail_table = joined_products[detail_key]

            # Determine the join type based on the join method. If the method
            # is "detail" then we need to swap the order of the tables
            # (products), because SQLAlchemy provides inteface only for
            # left-outer join.
            if join.method == "match":
                is_outer = False
            elif join.method == "master":
                is_outer = True
            elif join.method == "detail":
                # Swap the master and detail tables to perform RIGHT OUTER JOIN
                master_table, detail_table = (detail_table, master_table)
                is_outer = True
                outer_details.append(detail_table)
            else:
                raise ModelError("Unknown join method '%s'" % join.method)


            product = sql.expression.join(master_table,
                                             detail_table,
                                             onclause=onclause,
                                             isouter=is_outer)

            del joined_products[detail_key]
            joined_products[master_key] = product

        if not joined_products:
            # This should not happen
            raise InternalError("No joined products left.")

        if len(joined_products) > 1:
            raise ModelError("Some tables are not joined: %s" %
                    (joined_products.keys()))

        # Return the remaining joined product
        result = joined_products.values()[0]

        return JoinProduct(result, outer_details)

    def column(self, attribute, locale=None):
        """Return a column object for attribute.

        `locale` is explicit locale to be used. If not specified, then the
        current locale is used for localizable attributes."""

        logical = self.mapper.logical(attribute, locale)
        if logical in self.logical_to_column:
            return self.logical_to_column[logical]

        ref = self.mapper.physical(attribute, locale)
        table = self.table(ref.schema, ref.table)

        try:
            column = table.c[ref.column]
        except:
            # FIXME: do not expose this exception to server
            avail = [str(c) for c in table.columns]
            raise BrowserError("Unknown column '%s' in table '%s' avail: %s" %
                                        (ref.column, ref.table, avail))

        # Extract part of the date
        if ref.extract:
            column = sql.expression.extract(ref.extract, column)
        if ref.func:
            column = getattr(sql.expression.func, ref.func)(column)
        if ref.expr:
            expr_func = eval(compile(ref.expr, '__expr__', 'eval'), _EXPR_EVAL_NS.copy())
            if not callable(expr_func):
                raise BrowserError("Cannot evaluate a callable object from reference's expr: %r" % ref)
            column = expr_func(column)
        if self.safe_labels:
            label = "a%d" % self.label_counter
            self.label_counter += 1
        else:
            label = logical

        if isinstance(column, basestring):
            raise ValueError("Cannot resolve %s to a column object: %r" % (attribute, column))

        column = column.label(label)

        self.logical_to_column[logical] = column
        self.column_to_logical[label] = logical

        return column

    def logical_labels(self, columns):
        """Returns list of logical attribute labels from list of columns
        or column labels.

        This method and additional internal references were added because some
        database dialects, such as Exasol, can not handle dots in column
        names, even when quoted.
        """

        # Should not this belong to the snowflake
        attributes = []

        for column in columns:
            attributes.append(self.column_to_logical.get(column.name,
                                                         column.name))

        return attributes

    def table(self, schema, table_name):
        """Return a SQLAlchemy Table instance. If table was already accessed,
        then existing table is returned. Otherwise new instance is created.

        If `schema` is ``None`` then browser's default schema is used.
        """

        aliased_ref = (schema or self.mapper.schema, table_name)

        if aliased_ref in self.tables:
            return self.tables[aliased_ref]

        # Get real table reference
        try:
            table_ref = self.table_aliases[aliased_ref]
        except KeyError:
            raise ModelError("Table with reference %s not found. "
                             "Missing join in cube '%s'?" %
                                    (aliased_ref, self.cube.name) )

        table = sqlalchemy.Table(table_ref.table, self.metadata,
                                 autoload=True, schema=table_ref.schema)

        if table_ref.alias:
            table = table.alias(table_ref.alias)

        self.tables[aliased_ref] = table

        return table


class StatementBuilder(object):
    def __init__(self, browser):
        """Creates a statement builder object – a controller-like object that
        incrementally constructs the statement.

        Result attributes:

        * `statement` – SQL query statement
        * `labels` – logical labels for the statement selection
        """

        self.browser = browser

        # Inherit
        # FIXME: really?
        self.logger = browser.logger
        self.mapper = browser.mapper
        self.cube = browser.cube

        self.snowflake = SnowflakeSchema(self.cube, self.mapper,
                                         self.browser.metadata,
                                         safe_labels=browser.safe_labels)

        # Fact table or a join product of match/master joined tables
        #
        # This is the main reason for this class
        self.master_fact = None
        self.drilldown = None

        # Output:
        self.statement = None
        self.labels = []

    def aggregation_statement(self, cell, drilldown=None, aggregates=None,
                              split=None, attributes=None):
        """Builds a statement to aggregate the `cell`."""

        # TODO: split
        # TODO: PTD!!!

        # TODO: add self.labels for builder.labels not statement.labels
        # FIXME: derive this:
        drilldown = drilldown or Drilldown()

        has_outer_details = False

        selection = []

        self.logger.debug("=== aggregate")
        master_attributes = set()
        master_conditions = self.conditions_for_cell(cell, master_fact=True)
        self.logger.debug("--- found %s master conditions" % len(master_conditions))

        for cond in master_conditions:
            self.logger.debug("--- condition: %s: %s"
                              % ([a.ref() for a in cond.attributes], cond.condition))
            master_attributes |= set(cond.attributes)

        self.logger.debug("--- master attributes: %s" % [a.ref() for a in master_attributes])

        # Aggregates
        # ----------

        if not aggregates:
            raise ArgumentError("List of aggregates sohuld not be empty")

        # Collect expressions of aggregate functions
        selection += self.builtin_aggregate_expressions(aggregates,
                                                        coalesce_measures=has_outer_details)
        # Collect drilldown attributes
        # ----------------------------
        # TODO: split to master/detail
        master_attributes |= set(drilldown.level_attributes())

        # Join
        # ----

        # Create the master join product:
        join_product = self.snowflake.join_expression(master_attributes)
        join_expression = join_product.expression

        # Drilldown – Group-by
        # --------------------
        #
        group_by = []

        for attribute in drilldown.level_attributes():
            column = self.column(attribute)
            group_by.append(column)
            selection.append(column)

        # Prepare the master_fact statement:
        self.logger.debug("--- SELECT: %s" % ([str(s) for s in selection],))
        self.logger.debug("--- FROM: %s" % (join_expression, ))
        master_fact = sql.expression.select(selection,
                                            from_obj=join_expression,
                                            use_labels=True,
                                            group_by=group_by)

        # TODO: Add periods-to-date condition

        if master_conditions:
            condition = condition_conjuction([c.condition for c in master_conditions])
            master_fact = master_fact.where(condition)

        # TODO: Where condition
        # Join outer details
        # ------------------

        # if detail_attributes:
        #    join_product = self.snowflake.join_expression(detail_attributes,
        #                                                fact=master_fact)
        statement = master_fact


        self.statement = statement
        self.labels = self.snowflake.logical_labels(statement.columns)

        # Used in order
        self.drilldown = drilldown
        self.split = split

        return self.statement

    def builtin_aggregate_expressions(self, aggregates,
                                      coalesce_measures=False):
        """Returns list of expressions for aggregates from `aggregates` that
        are computed using the SQL statement.
        """

        expressions = []
        for agg in aggregates:
            exp = self.aggregate_expression(agg, coalesce_measures)
            if exp is not None:
                expressions.append(exp)

        return expressions

    def aggregate_expression(self, aggregate, coalesce_measure=False):
        """Returns an expression that performs the aggregation of measure
        `aggregate`. The result's label is the aggregate's name.  `aggregate`
        has to be `MeasureAggregate` instance.

        If aggregate function is post-aggregation calculation, then `None` is
        returned.

        Aggregation function names are case in-sensitive.

        If `coalesce_measure` is `True` then selected measure column is wrapped
        in ``COALESCE(column, 0)``.
        """
        # TODO: support aggregate.expression

        if aggregate.expression:
            raise NotImplementedError("Expressions are not yet implemented")

        # If there is no function specified, we consider the aggregate to be
        # computed in the mapping
        if not aggregate.function:
            # TODO: this should be depreciated in favor of aggreate.expression
            # TODO: Following expression should be raised instead:
            # raise ModelError("Aggregate '%s' has no function specified"
            #                 % str(aggregate))
            column = self.column(aggregate)
            # TODO: add COALESCE()
            return column

        function_name = aggregate.function.lower()
        function = self.browser.builtin_function(function_name, aggregate)

        if not function:
            return None

        expression = function(aggregate, self, coalesce_measure)

        return expression

    def conditions_for_cell(self, cell, master_fact=True):
        """Constructs conditions for all cuts in the `cell`. Returns a list of
        tuple with attributes:

        * ``condition`` – SQL conditional expression
        * ``attributes`` – list of attributes in the expression
        * ``is_outer_detail`` – `True` if one of the attributes is joined as
          `detail`
        """

        # TODO: master_fact is ignored for now

        if not cell:
            return []

        conditions = []

        for cut in cell.cuts:
            dim = self.cube.dimension(cut.dimension)

            if isinstance(cut, PointCut):
                path = cut.path
                condition = self.condition_for_point(dim, path, cut.hierarchy,
                                                     cut.invert)

            elif isinstance(cut, SetCut):
                set_conds = []

                for path in cut.paths:
                    element_condition = self.condition_for_point(dim, path,
                                                                 cut.hierarchy,
                                                                 False)
                    set_conds.append(wrapped_cond.condition)
                    attributes |= wrapped_cond.attributes

                condition = sql.expression.or_(*set_conds)
                if cut.invert:
                    condition = sql.expression.not_(condition)

            elif isinstance(cut, RangeCut):
                range_cond = self.range_condition(cut.dimension,
                                                  cut.hierarchy,
                                                  cut.from_path,
                                                  cut.to_path, cut.invert)
                condition = range_cond.condition
                attributes |= range_cond.attributes

            else:
                raise ArgumentError("Unknown cut type %s" % type(cut))

            conditions.append(condition)

        return conditions

    def condition_for_point(self, dim, path, hierarchy=None, invert=False):
        """Returns a `Condition` tuple (`attributes`, `conditions`,
        `group_by`) dimension `dim` point at `path`. It is a compound
        condition - one equality condition for each path element in form:
        ``level[i].key = path[i]``"""

        attributes = set()
        conditions = []

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise ArgumentError("Path has more items (%d: %s) than there are levels (%d) "
                                "in dimension %s" % (len(path), path, len(levels), dim.name))

        # level_condition = None

        last_level = levels[-1] if len(levels) else None

        for level, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level.key)
            conditions.append(column == value)

            # FIXME: join attributes only if details are requested
            # Collect grouping columns
            for attr in level.attributes:
                attributes.add(attr)

        # if level_condition:
        #    conditions.append(level_condition.condition)
        #    attributes = attributes | level_condition.attributes

        condition = sql.expression.and_(*conditions)

        if invert:
            condition = sql.expression.not_(condition)

        return Condition(attributes,condition)

    def range_condition(self, dim, hierarchy, from_path, to_path, invert=False):
        """Return a condition for a hierarchical range (`from_path`,
        `to_path`). Return value is a `Condition` tuple."""

        dim = self.cube.dimension(dim)

        lower, lower_ptd = self._boundary_condition(dim, hierarchy, from_path, 0)
        upper, upper_ptd = self._boundary_condition(dim, hierarchy, to_path, 1)

        ptd_condition = lower_ptd or upper_ptd

        conditions = []
        attributes = set()
        if lower.condition is not None:
            conditions.append(lower.condition)
            attributes |= lower.attributes
        if upper.condition is not None:
            conditions.append(upper.condition)
            attributes |= upper.attributes

        if ptd_condition and ptd_condition.condition is not None:
            conditions.append(ptd_condition.condition)
            attributes |= ptd_condition.attributes

        condexpr = sql.expression.and_(*conditions) if len(conditions) > 1 else conditions[0]

        if invert:
            condexpr = sql.expression.not_(condexpr)

        return Condition(attributes, condexpr)

    def _boundary_condition(self, dim, hierarchy, path, bound, first=True):
        """Return a `Condition` tuple for a boundary condition. If `bound` is
        1 then path is considered to be upper bound (operators < and <= are
        used), otherwise path is considered as lower bound (operators > and >=
        are used )"""

        if not path:
            return (Condition(set(), None), None)

        last, ptd_condition = self._boundary_condition(dim, hierarchy, path[:-1], bound, first=False)

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise ArgumentError("Path has more items (%d: %s) than there are levels (%d) "
                                "in dimension %s" % (len(path), path, len(levels), dim.name))

        attributes = set()
        conditions = []

        # last_level = levels[-1] if len(levels) else None

        for level, value in zip(levels[:-1], path[:-1]):
            column = self.column(level.key)
            conditions.append(column == value)

            for attr in level.attributes:
                attributes.add(attr)

        # Select required operator according to bound
        # 0 - lower bound
        # 1 - upper bound
        if bound == 1:
            # 1 - upper bound (that is <= and < operator)
            operator = sql.operators.le if first else sql.operators.lt
        else:
            # else - lower bound (that is >= and > operator)
            operator = sql.operators.ge if first else sql.operators.gt

        column = self.column(levels[-1].key)
        conditions.append( operator(column, path[-1]) )

        for attr in levels[-1].attributes:
            attributes.add(attr)

        condition = sql.expression.and_(*conditions)
        attributes |= last.attributes

        # if last.condition is not None:
        #    condition = sql.expression.or_(condition, last.condition)
        #    attributes |= last.attributes

        return (Condition(attributes, condition), ptd_condition)

    def column(self, attribute, locale=None):
        """Returns either a physical column for the attribute or a reference to
        a column from the master fact if it exists."""

        if self.master_fact:
            ref = self.mapper.physical(attribute, locale)
            self.logger.debug("column %s (%s) - master" % (attribute.ref(), ref))
            return self.master_fact.c[ref.column]
        else:
            self.logger.debug("column %s - snowflake" % (attribute.ref(), ))
            return self.snowflake.column(attribute, locale)

    def paginate(self, page, page_size):
        """Returns paginated statement if page is provided, otherwise returns
        the same statement."""

        if page is not None and page_size is not None:
            self.statement = self.statement.offset(page * page_size).limit(page_size)

        return self.statement

    def order(self, order):
        """Returns a SQL statement which is ordered according to the `order`. If
        the statement contains attributes that have natural order specified, then
        the natural order is used, if not overriden in the `order`.

        `order` sohuld be prepared using
        :meth:`AggregationBrowser.prepare_order`.

        `dimension_levels` is list of considered dimension levels in form of
        tuples (`dimension`, `hierarchy`, `levels`). For each level it's sort
        key is used.
        """

        # Each attribute mentioned in the order should be present in the selection
        # or as some column from joined table. Here we get the list of already
        # selected columns and derived aggregates

        selection = collections.OrderedDict()

        # Get logical attributes from column labels (see logical_labels method
        # description for more information why this step is necessary)
        for column, ref in zip(self.statement.columns, self.labels):
            selection[ref] = column

        # Make sure that the `order` is a list of of tuples (`attribute`,
        # `order`). If element of the `order` list is a string, then it is
        # converted to (`string`, ``None``).

        order = order or []

        drilldown = self.drilldown or []

        for dditem in drilldown:
            dim, hier, levels = dditem[0:3]
            for level in levels:
                level = dim.level(level)
                if level.order:
                    order.append( (level.order_attribute.ref(), level.order) )

        order_by = collections.OrderedDict()

        if self.split:
            split_column = sql.expression.column(SPLIT_DIMENSION_NAME)
            order_by[SPLIT_DIMENSION_NAME] = split_column

        # Collect the corresponding attribute columns
        for attribute, order_dir in order:
            try:
                column = selection[attribute.ref()]
            except KeyError:
                attribute = self.mapper.attribute(attribute.ref())
                column = self.column(attribute)

            column = order_column(column, order_dir)

            if attribute.ref() not in order_by:
                order_by[attribute.ref()] = column

        # Collect natural order for selected columns
        for (name, column) in selection.items():
            try:
                # Backward mapping: get Attribute instance by name. The column
                # name used here is already labelled to the logical name
                attribute = self.mapper.attribute(name)
            except KeyError:
                # Since we are already selecting the column, then it should
                # exist this exception is raised when we are trying to get
                # Attribute object for an aggregate - we can safely ignore
                # this.

                # TODO: add natural ordering for measures (may be nice)
                attribute = None

            if attribute and attribute.order and name not in order_by.keys():
                order_by[name] = order_column(column, attribute.order)

        self.statement = self.statement.order_by(*order_by.values())

        return self.statement


"""A Condition representation. `attributes` - list of attributes involved in
the conditions, `conditions` - SQL conditions"""
Condition = collections.namedtuple("Condition",
                                   ["attributes", "condition"])



JoinProduct = collections.namedtuple("JoinProduct",
                                        ["expression", "outer_details"])


def condition_conjuction(conditions):
    """Do conjuction of conditions if there are more than one, otherwise just
    return the single condition."""
    if not conditions:
        return None
    elif len(conditions):
        return conditions[0]
    else:
        return sql.expression.and_(*conditions)

def order_column(column, order):
    """Orders a `column` according to `order` specified as string."""

    if not order:
        return column
    elif order.lower().startswith("asc"):
        return column.asc()
    elif order.lower().startswith("desc"):
        return column.desc()
    else:
        raise ArgumentError("Unknown order %s for column %s") % (order, column)


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
