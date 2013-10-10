# -*- coding=utf -*-

from ...browser import Drilldown
from ...errors import *
from collections import namedtuple, OrderedDict
from .mapper import DEFAULT_KEY_FIELD
from .utils import condition_conjuction, order_column

try:
    import sqlalchemy
    import sqlalchemy.sql as sql

except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")


__all__ = [
    "SnowflakeSchema",
    "QueryBuilder"
]


SnowflakeAttribute = namedtuple("SnowflakeAttribute", ["attribute", "join"])

"""Aliased table information"""
SnowflakeTable = namedtuple("SnowflakeTable",
                            ["schema", "table", "alias", "join"])


MATCH_MASTER_RSHIP = 1
OUTER_DETAIL_RSHIP = 2


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

        self.fact_key_column = self.fact_table.c[self.fact_key].label(self.fact_key)

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

        # Table -> relationship type
        # Prepare maps of attributes -> relationship type
        relationships = self.analyse_fact_relationships(for_aggregation=False)
        attributes = self.cube.get_attributes(aggregated=False)
        tables = self.mapper.tables_for_attributes(attributes)
        tables = dict(zip(attributes, tables))
        mapping = {}
        for attribute in attributes:
            mapping[attribute] = relationships[tables[attribute]]

        self.fact_relationships = mapping

        relationships = self.analyse_fact_relationships(for_aggregation=True)
        attributes = self.cube.get_attributes(aggregated=True)
        tables = self.mapper.tables_for_attributes(attributes)
        tables = dict(zip(attributes, tables))
        mapping = {}
        for attribute in attributes:
            mapping[attribute] = relationships[tables[attribute]]

        self.aggregated_fact_relationships = mapping

    def is_outer_detail(self, attribute, for_aggregation=False):
        """Returns `True` if the attribute belongs to an outer-detail table."""
        if for_aggregation:
            lookup = self.aggregated_fact_relationships
        else:
            lookup = self.fact_relationships

        try:
            return lookup[attribute] == OUTER_DETAIL_RSHIP
        except KeyError:
            raise InternalError("No fact relationship for attribute %s "
                                "(aggregate: %s)"
                                % (attribute.ref(), for_aggregation))

    def analyse_fact_relationships(self, for_aggregation=False):
        """ Analyses the schema and stores the information. Stored information
        contains:

        * attribute ownership by a table
        * table join type: master/match or detail (outer)

        The rule for marking tables is as follows:

        * if a table is connected to a fact or other master/detail table by
          master/detail then it will be considered master/detail
        * if a table is connected to an outer detail it is considered to be
          outer detail (in relationship to the fact), regardless of it's join
          type
        * if a table is connected through outer detail to any kind of table,
          then it will stay as detail
        """

        attributes = self.cube.get_attributes(aggregated=for_aggregation)
        # This should return all joins
        joins = self.mapper.relevant_joins(attributes)

        if len(joins) != len(self.mapper.joins):
            raise InternalError("Not all joins are considered for analysis")

        # Dictionary of raw tables and their joined products
        # table-to-master relationships:
        #     MASTER_MATCH_RSHIP: either joined as "match" or "master"
        #     OUTER_DETAIL_RSHIP: joined as "detail"
        fact_relationships = {}

        # Anchor the fact table
        table = (self.schema, self.fact_name)
        fact_relationships[table] = MATCH_MASTER_RSHIP

        # Collect all the tables first:
        for join in joins:
            # Add master table to the list
            table = (join.master.schema, join.master.table)
            if table not in fact_relationships:
                fact_relationships[table] = None

            # Add (aliased) detail table to the rist
            table = (join.detail.schema, join.alias or join.detail.table)
            if table not in fact_relationships:
                fact_relationships[table] = None
            else:
                raise ModelError("Joining detail table %s twice" % (table, ))

        # Analyse the joins

        for join in joins:
            master_key = (join.master.schema, join.master.table)
            detail_key = (join.detail.schema, join.alias or join.detail.table)

            if fact_relationships.get(detail_key):
                raise InternalError("Detail %s already classified" % detail_key)

            master_rs = fact_relationships[master_key]

            if master_rs is None:
                raise InternalError("Joining to unclassified master. %s->%s"
                                    % (master_key, defailt_key))
            elif master_rs == MATCH_MASTER_RSHIP \
                    and join.method in ("match", "master"):
                relationship = MATCH_MASTER_RSHIP
            elif master_rs == OUTER_DETAIL_RSHIP \
                    or join.method == "detail":
                relationship = OUTER_DETAIL_RSHIP
            else:
                raise InternalError("Unknown relationship combination for "
                                    "%s(%s)->%s(%s)"
                                    % (master_key, master_rs,
                                       detail_key, join.method))

            fact_relationships[detail_key] = relationship

        return fact_relationships

    def join_expression(self, attributes, include_fact=True, fact=None):
        """Create partial expression on a fact table with `joins` that can be
        used as core for a SELECT statement. `join` is a list of joins
        returned from mapper (most probably by `Mapper.relevant_joins()`)

        Returns a QLAlchemy expression object.

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
            raise ModelError("Some tables are not joined: %s"
                             % (joined_products.keys(), ))

        # Return the remaining joined product
        result = joined_products.values()[0]

        return result

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
            raise BrowserError("Unknown column '%s' in table '%s' avail: %s"
                               % (ref.column, ref.table, avail))

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
                             "Missing join in cube '%s'?"
                             % (aliased_ref, self.cube.name) )

        table = sqlalchemy.Table(table_ref.table, self.metadata,
                                 autoload=True, schema=table_ref.schema)

        if table_ref.alias:
            table = table.alias(table_ref.alias)

        self.tables[aliased_ref] = table

        return table


class QueryBuilder(object):
    def __init__(self, browser):
        """Creates a SQL query statement builder object – a controller-like
        object that incrementally constructs the statement.

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

        self.master_fact = None

        # Intermediate results
        self.drilldown = None
        self.split = None

        # Output:
        self.statement = None
        self.labels = []

    def aggregation_statement(self, cell, drilldown=None, aggregates=None,
                              split=None, attributes=None):
        """Builds a statement to aggregate the `cell`."""

        # TODO: split
        # TODO: PTD!!!

        # TODO: we are expeced to get this prepared!
        drilldown = drilldown or Drilldown()

        # The selection: aggregates + drill-down attributes
        selection = []

        self.logger.debug("=== aggregate")
        self.logger.debug("--- cell: %s" % ",".join([str(cut) for cut in cell.cuts]))
        self.logger.debug("--- drilldown: %s" % drilldown)

        # Analyse and Prepare
        # -------------------
        # Get the cell attributes and find whether we have some outer details
        #
        cut_attributes = self.attributes_for_cell_cuts(cell)
        drilldown_attributes = drilldown.all_attributes()
        master_attributes = []
        master_cuts = []
        detail_attributes = []
        detail_cuts = []

        for cut, attributes in cut_attributes:
            for a in attributes:
                self.logger.debug("--- A(%s): %s" % (type(a), a))
            is_outer_detail = [self.snowflake.is_outer_detail(a) for a in attributes]

            if all(is_outer_detail):
                detail_attributes += attributes
                detail_cuts.append(cut)
            else:
                if any(is_outer_detail):
                    raise InternalError("Cut %s spreading from master to "
                                        "outer detail is not supported."
                                        % str(cut))
                else:
                    master_attributes += attributes
                    master_cuts.append(cut)

        # Used to determine whether we need to have master fact and outer joins
        # construction or we are fine with just one joined construct.
        has_outer_detail_condition = len(detail_cuts) > 0

        for attribute in drilldown_attributes:
            if self.snowflake.is_outer_detail(attribute):
                detail_attributes.append(attribute)
            else:
                master_attributes.append(attribute)

        self.logger.debug("master attributes: %s"
                          % [a.ref() for a in master_attributes])
        self.logger.debug("detail attributes: %s"
                          % [a.ref() for a in detail_attributes])

        # Used to determine whether to coalesce attributes.
        has_outer_details = len(detail_attributes) > 0

        self.logger.debug("composition: detail conditions: %s other: %s"
                          % (has_outer_detail_condition, has_outer_details))
        # Cases:
        # MASTER-ONLY - we have only master condition
        # DETAIL-ONLY – we have only detail condition
        # MASTER-DETAIL – we have condition in master and in detail

        self.logger.debug("getting cond for master cuts: %s" % (master_cuts, ))
        master_conditions = self.conditions_for_cuts(master_cuts)

        # Aggregates
        # ----------

        if not aggregates:
            raise ArgumentError("List of aggregates sohuld not be empty")

        # Collect expressions of aggregate functions
        # TODO: check the Robin's requirement on measure coalescing
        selection += self.builtin_aggregate_expressions(aggregates,
                                                        coalesce_measures=has_outer_details)

        if not has_outer_detail_condition:
            # Collect drilldown attributes
            # ----------------------------
            # TODO: split to master/detail
            attributes = set(master_attributes) | set(detail_attributes)

            # Drilldown – Group-by
            # --------------------
            #
            group_by = []

            for attribute in drilldown_attributes:
                column = self.column(attribute)
                group_by.append(column)
                selection.append(column)

            # Join
            # ----

            # Create the master join product:
            join_expression = self.snowflake.join_expression(attributes)

            # WHERE Condition
            # ---------
            if master_conditions:
                condition = condition_conjuction([c.condition for c in master_conditions])
            else:
                condition = None

            # Prepare the master_fact statement:
            self.logger.debug("-a- JOIN: %s" % str(join_expression))
            self.logger.debug("-a- WHERE: %s" % str(condition))
            statement = sql.expression.select(selection,
                                              from_obj=join_expression,
                                              use_labels=True,
                                              whereclause=condition,
                                              group_by=group_by)

        else:
            raise NotImplementedError("Outer detail is not implemented")

        # TODO: Add periods-to-date condition

        self.statement = statement
        self.labels = self.snowflake.logical_labels(statement.columns)
        self.logger.debug("labels: %s" % self.labels)

        # Used in order
        self.drilldown = drilldown
        self.split = split

        return self.statement

    def denormalized_statement(self, cell=None, attributes=None,
                               expand_locales=False, include_fact_key=True):
        """Builds a statement for denormalized view. `whereclause` is same as
        SQLAlchemy `whereclause` for `sqlalchemy.sql.expression.select()`.
        `attributes` is list of logical references to attributes to be
        selected. If it is ``None`` then all attributes are used.
        `condition_attributes` contains list of attributes that are not going
        to be selected, but are required for WHERE condition.

        Set `expand_locales` to ``True`` to expand all localized attributes.
        """

        if attributes is None:
            attributes = self.cube.all_attributes()

        join_attributes = set(attributes) | self.attributes_for_cell(cell)
        join_expression = self.snowflake.join_expression(attributes)

        columns = self.snowflake.columns(attributes, expand_locales=expand_locales)

        if include_fact_key:
            columns.insert(0, self.snowflake.fact_key_column)

        if cell:
            condition = self.condition_for_cell(cell)
        else:
            condition = None

        statement = sql.expression.select(columns,
                                          from_obj=join_expression,
                                          use_labels=True,
                                          whereclause=condition)

        self.statement = statement
        self.labels = self.snowflake.logical_labels(statement.columns)

        return statement

    def fact(self, id_):
        """Selects only fact with given id"""
        condition = self.snowflake.fact_key_column == id_
        return self.append_condition(condition)

    def append_condition(self, condition):
        """Appends `condition` to the generated statement."""
        self.statement = self.statement.where(condition)
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

    def attributes_for_cell(self, cell):
        """Returns a set of attributes included in the cell."""
        if not cell:
            return set()

        attributes = set()
        for cut, cut_attrs in self.attributes_for_cell_cuts(cell):
            attributes |= set(cut_attrs)
        return attributes

    def attributes_for_cell_cuts(self, cell):
        """Returns a list of tuples (`cute`, `attributes`) where `attributes`
        is list of attributes involved in the `cut`."""

        # Note: this method belongs here, not to the Cell class, as we might
        # discover that some other attributes might be required for the cell
        # (in the future...)

        result = []

        for cut in cell.cuts:
            depth = cut.level_depth()
            if depth:
                dim = self.cube.dimension(cut.dimension)
                hier = dim.hierarchy(cut.hierarchy)
                keys = (level.key for level in hier[0:depth])
                result.append((cut, keys))

        return result

    def condition_for_cell(self, cell):
        """Returns a SQL condition for the `cell`."""
        conditions = self.conditions_for_cuts(cell.cuts)
        condition = condition_conjuction(conditions)

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

        conditions = []

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise ArgumentError("Path has more items (%d: %s) than there are levels (%d) "
                                "in dimension %s" % (len(path), path, len(levels), dim.name))

        for level, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level.key)
            conditions.append(column == value)

        condition = sql.expression.and_(*conditions)

        if invert:
            condition = sql.expression.not_(condition)

        return condition

    def range_condition(self, dim, hierarchy, from_path, to_path, invert=False):
        """Return a condition for a hierarchical range (`from_path`,
        `to_path`). Return value is a `Condition` tuple."""

        dim = self.cube.dimension(dim)

        lower, lower_ptd = self._boundary_condition(dim, hierarchy, from_path, 0)
        upper, upper_ptd = self._boundary_condition(dim, hierarchy, to_path, 1)

        conditions = []
        if lower.condition is not None:
            conditions.append(lower.condition)
        if upper.condition is not None:
            conditions.append(upper.condition)

        condition = condition_conjuction(conditions)

        if invert:
            condition = sql.expression.not_(condexpr)

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
            column = self.column(level.key)
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

        column = self.column(levels[-1].key)
        conditions.append(operator(column, path[-1]))

        condition = condition_conjuction(conditions)

        if last is not None:
            condition = sql.expression.or_(condition, last)

        return condition

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

        selection = OrderedDict()

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
                    order.append((level.order_attribute.ref(), level.order))

        order_by = OrderedDict()

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
