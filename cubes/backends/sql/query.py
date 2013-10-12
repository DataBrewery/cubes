# -*- coding=utf -*-

from ...browser import Drilldown, Cell, PointCut, SetCut, RangeCut
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


"""Product of join_expression"""
JoinedProduct = namedtuple("JoinedProduct",
        ["expression", "tables"])

MATCH_MASTER_RSHIP = 1
OUTER_DETAIL_RSHIP = 2

class SnowflakeTable(object):
    def __init__(self, schema, name, alias=None, table=None, join=None):
        self.schema = schema
        self.name = name
        self.table = table
        self.alias = alias
        self.join = join

    @property
    def key(self):
        return (self.schema, self.aliased_name)

    @property
    def aliased_name(self):
        return self.alias or self.name

# TODO: merge this with mapper
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

        # Collect all tables and their aliases.
        #
        # table_aliases contains mapping between aliased table name and real
        # table name with alias:
        #
        #       (schema, aliased_name) --> (schema, real_name, alias)
        #

        # Mapping where keys are attributes and values are columns
        self.logical_to_column = {}
        # Mapping where keys are column labels and values are attributes
        self.column_to_logical = {}

        # Collect tables from joins

        self.tables = {}
        # Table -> relationship type
        # Prepare maps of attributes -> relationship type
        self.fact_relationships = {}
        self.aggregated_fact_relationships = {}

        self._collect_tables()

    def _collect_tables(self):
        """Collect tables in the schema. Analyses their relationship towards
        the fact table.

        Stored information contains:

        * attribute ownership by a table
        * relationship type of tables towards the fact table: master/match or
          detail (outer)

        The rule for deciding the table relationship is as follows:

        * if a table is connected to a fact or other master/detail table by
          master/detail then it will be considered master/detail
        * if a table is connected to an outer detail it is considered to be
          outer detail (in relationship to the fact), regardless of it's join
          type
        * if a table is connected through outer detail to any kind of table,
          then it will stay as detail
        """

        # Collect the fact table as the root master table
        #
        table = SnowflakeTable(self.schema, self.fact_name,
                               table=self.fact_table)
        self.tables[table.key] = table

        # Collect all the detail tables
        # 
        for join in self.mapper.joins:
            # just ask for the table

            sql_table = sqlalchemy.Table(join.detail.table,
                                         self.metadata,
                                         autoload=True,
                                         schema=join.detail.schema)

            if join.alias:
                sql_table = sql_table.alias(join.alias)

            table = SnowflakeTable(schema=join.detail.schema,
                                   name=join.detail.table,
                                   alias=join.alias,
                                   join=join,
                                   table=sql_table)

            self.tables[table.key] = table

        # Analyse relationships
        # ---------------------

        # Dictionary of raw tables and their joined products
        # table-to-master relationships:
        #     MASTER_MATCH_RSHIP: either joined as "match" or "master"
        #     OUTER_DETAIL_RSHIP: joined as "detail"
        relationships = {}

        # Anchor the fact table
        key = (self.schema, self.fact_name)
        relationships[key] = MATCH_MASTER_RSHIP
        self.tables[key].relationship = MATCH_MASTER_RSHIP

        # Collect all the tables first:
        for join in self.mapper.joins:
            # Add master table to the list
            table = (join.master.schema, join.master.table)
            if table not in relationships:
                fact_relationships[table] = None

            # Add (aliased) detail table to the rist
            table = (join.detail.schema, join.alias or join.detail.table)
            if table not in relationships:
                relationships[table] = None
            else:
                raise ModelError("Joining detail table %s twice" % (table, ))

        # Analyse the joins
        for join in self.mapper.joins:
            master_key = (join.master.schema, join.master.table)
            detail_key = (join.detail.schema, join.alias or join.detail.table)

            if relationships.get(detail_key):
                raise InternalError("Detail %s already classified" % detail_key)

            master_rs = relationships[master_key]

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

            relationships[detail_key] = relationship
            self.tables[detail_key].relationship = relationship


        # Prepare relationships of attributes
        #
        # TODO: make SnowflakeAttribute class
        attributes = self.cube.get_attributes(aggregated=False)
        tables = self.mapper.tables_for_attributes(attributes)
        tables = dict(zip(attributes, tables))
        mapping = {}
        for attribute in attributes:
            mapping[attribute] = relationships[tables[attribute]]
        self.fact_relationships = mapping

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

    def join_expression(self, attributes, include_fact=True, fact=None,
                        fact_columns=None):
        """Create partial expression on a fact table with `joins` that can be
        used as core for a SELECT statement. `join` is a list of joins
        returned from mapper (most probably by `Mapper.relevant_joins()`)

        `fact_columns` is a dictionary where keys are tuples (`table`,
        `column`) and values are columns from `fact`. This is used for
        composing aggregate statement under certain conditions.

        Returns a tuple: (`expression`, `tables`) where `expression` is
        QLAlchemy expression object and `tables` is a list of keys of joined
        tables.

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

        fact_columns = fact_columns or {}
        fact_key = (self.schema, self.fact_name)

        tables = []

        if include_fact:
            if fact is not None:
                joined_products[fact_key] = fact
            else:
                joined_products[fact_key] = self.fact_table
            tables.append(fact_key)

        # Collect all the tables first:
        for join in joins:
            if not join.detail.table or (join.detail.table == self.fact_name and not join.alias):
                raise MappingError("Detail table name should be present and "
                                   "should not be a fact table unless aliased.")

            # Add master table to the list. If fact table (or statement) was
            # explicitly specified, use it instead of the original fact table
            if fact is not None and (join.master.schema, join.master.table) == fact_key:
                table = fact
            else:
                table = self.table(join.master.schema, join.master.table)
            joined_products[(join.master.schema, join.master.table)] = table

            # Add (aliased) detail table to the rist
            table = self.table(join.detail.schema, join.alias or join.detail.table)
            key = (join.detail.schema, join.alias or join.detail.table)
            joined_products[key] = table
            tables.append(key)

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
            if fact is not None and (join.master.schema, join.master.table) == fact_key:
                key = (join.master.schema, join.master.table, join.master.column)
                try:
                    master_column = fact_columns[key]
                except KeyError:
                    raise InternalError("Missing fact column %s" % (key, ))
                print "--- got it from fcs"
            else:
                master_table = self.table(master.schema, master.table)

                try:
                    master_column = master_table.c[master.column]
                except KeyError:
                    raise ModelError('Unable to find master key (schema %s) '
                                     '"%s"."%s" ' % join.master[0:3])
                print "--- got it from tables"

            detail_table = self.table(join.detail.schema, join.alias or join.detail.table)
            try:
                detail_column = detail_table.c[detail.column]
            except KeyError:
                raise ErrorMappingError('Unable to find detail key (schema %s) "%s"."%s" ' \
                                    % join.detail[0:3])

            # The join condition:
            print "--- JOIN on %s(%s) -> %s(%s)" % \
                    (master_column, type(master_column), detail_column,
                            type(detail_column))
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

        return JoinedProduct(result, joined_products)

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

        key = (schema or self.mapper.schema, table_name)
        # Get real table reference
        try:
            return self.tables[key].table
        except KeyError:
            raise ModelError("Table with reference %s not found. "
                             "Missing join in cube '%s'?"
                             % (key, self.cube.name) )


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

        if not aggregates:
            raise ArgumentError("List of aggregates sohuld not be empty")

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

        master_cut_attributes = []
        master_attributes = []
        master_cuts = []

        detail_cut_attributes = []
        detail_attributes = []
        detail_cuts = []

        for cut, attributes in cut_attributes:
            is_outer_detail = [self.snowflake.is_outer_detail(a) for a in attributes]

            if all(is_outer_detail):
                detail_cut_attributes += attributes
                detail_cuts.append(cut)
            else:
                if any(is_outer_detail):
                    raise InternalError("Cut %s spreading from master to "
                                        "outer detail is not supported."
                                        % str(cut))
                else:
                    master_cut_attributes += attributes
                    master_cuts.append(cut)

        for attribute in drilldown_attributes:
            if self.snowflake.is_outer_detail(attribute):
                detail_attributes.append(attribute)
            else:
                master_attributes.append(attribute)

        self.logger.debug("MASTER selection: %s"
                          % [a.ref() for a in master_attributes])
        self.logger.debug("MASTER cut: %s"
                          % [a.ref() for a in master_cut_attributes])
        self.logger.debug("DETAIL selection: %s"
                          % [a.ref() for a in detail_attributes])
        self.logger.debug("DETAIL cut: %s"
                          % [a.ref() for a in detail_cut_attributes])

        # Used to determine whether to coalesce attributes.
        has_outer_details = len(detail_attributes)+len(detail_cut_attributes) > 0

        # Cases:
        # MASTER-ONLY - we have only master condition
        # DETAIL-ONLY – we have only detail condition
        # MASTER-DETAIL – we have condition in master and in detail

        master_conditions = self.conditions_for_cuts(master_cuts)
        detail_conditions = self.conditions_for_cuts(detail_cuts)

        # Pick the method:
        #
        # M - master, D - detail
        # C - condition, A - selection attributes (drilldown)
        #
        #    MA MC DA DC | method
        #    ============|=======
        #  0 -- -- -- -- | simple MC
        #  1 xx -- -- -- | simple MC
        #  2 -- xx -- -- | simple MC
        #  3 xx xx -- -- | simple MC
        #  4 -- -- xx -- | simple MC
        #  5 xx -- xx -- | simple MC
        #  6 -- -- -- xx | simple DC
        #  7 xx -- -- xx | simple DC
        #  8 -- xx xx -- | composed with MC as core
        #  9 xx xx xx -- | composed with MC as core
        # 10 -- -- xx xx | composed with DC as core
        # 11 xx -- xx xx | composed with DC as core
        # 12 -- xx -- xx | composed with MC as core, DC as outer
        # 13 xx xx -- xx | composed with MC as core, DC as outer
        # 14 -- xx xx xx | composed with MC as core, DC as outer
        # 15 xx xx xx xx | composed with MC as core, DC as outer

        if not detail_cut_attributes and not detail_attributes:
            # Cases: 0,1,2,3
            # We keep all masters as master, there is nothing in details
            simple_method = True
            has_outer_details = False
        elif not detail_cut_attributes and not master_cut_attributes:
            # Cases 4, 5
            # We keep the masters, just append details into selection/drilldown
            simple_method = True
            has_outer_details = True
            master_attributes += detail_attributes
        elif detail_cut_attributes \
                and not (master_cut_attributes or detail_attributes):
            # Cases 6, 7
            # Use detail cut as master cut, as we have no other cuts
            simple_method = True
            has_outer_details = False
            master_cut_attributes = detail_cut_attributes
        elif not detail_cut_attributes:
            # Case 8, 9
            simple_method = False
            has_outer_details = True
        else:
            raise NotImplementedError

        # Aggregates
        # ----------

        # Start the selection with aggregates
        # Collect expressions of aggregate functions
        # TODO: check the Robin's requirement on measure coalescing
        aggregate_selection = self.builtin_aggregate_expressions(aggregates,
                                                       coalesce_measures=has_outer_details)
        aggregate_labels = [c.label for c in aggregate_selection]

        if simple_method:
            self.logger.debug("using SIMPLE method")
            # Drilldown – Group-by
            # --------------------
            #
            group_by = []

            selection = aggregate_selection
            for attribute in master_attributes:
                column = self.column(attribute)
                group_by.append(column)
                selection.append(column)

            # Join
            # ----

            # Create the master join product:
            attributes = set(aggregates)
            attributes |= set(master_attributes)
            attributes |= set(master_cut_attributes)
            join_product = self.snowflake.join_expression(attributes)
            join_expression = join_product.expression

            # WHERE Condition
            # ---------
            condition = condition_conjuction(master_conditions)

            # Prepare the master_fact statement:
            statement = sql.expression.select(selection,
                                              from_obj=join_expression,
                                              use_labels=True,
                                              whereclause=condition,
                                              group_by=group_by)

        else:
            self.logger.debug("using COMPOSED method")

            # 1. MASTER FACT
            # ==============


            attributes = set(master_attributes) | set(master_cut_attributes)
            join_product = self.snowflake.join_expression(attributes)
            join_expression = join_product.expression

            # Store a map of joined columns for later
            # The map is: (schema, table, column) -> column

            master_fact_columns = {}
            for c in join_expression.columns:
                master_fact_columns[(c.table.schema, c.table.name, c.name)] = c

            # Prepare the selection
            selection = aggregate_selection
            # TODO: only relevant
            for attribute in attributes:
                column = self.column(attribute)
                selection.append(column)

            # WHERE Condition
            # ---------------
            condition = condition_conjuction(master_conditions)

            # Prepare the master_fact statement:
            statement = sql.expression.select(selection,
                                              from_obj=join_expression,
                                              use_labels=True,
                                              whereclause=condition)

            # From now-on the self.column() method will return columns from
            # master_fact.
            # statement = statement.alias(self.snowflake.fact_name)
            print "==> MASTER statement:", statement
            self.master_fact = statement
            print "--- master columns: %s" % (master_fact_columns, )

            # 2. OUTER DETAILS
            # ================
            attributes = set(detail_attributes) | set(detail_cut_attributes)
            join = self.snowflake.join_expression(attributes,
                                                  fact=self.master_fact,
                                                  fact_columns=master_fact_columns)

            join_expression = join.expression
            print "=== DETAIL JOIN: %s" % str(join_expression)
            # Add drilldown – Group-by
            # ------------------------
            #
            group_by = []

            # Append detail coluns to the master selection
            attributes = set(detail_attributes)
            attributes |= set(detail_cut_attributes)

            selection = list(join_expression.columns)
            # selection = []
            for attribute in attributes:
                column = self.column(attribute)
                group_by.append(column)
                # selection.append(column)

            # Join
            # ----

            condition = condition_conjuction(detail_conditions)
            print "=== DETAIL STATEMENT"
            print "--- selection:"
            for s in selection:
                print "---     %s(%s)" % (str(s), type(s))
            print "--> JOIN: %s" % str(join_expression)
            print "--> WHERE: %s" % str(condition)
            statement = sql.expression.select(selection,
                                              from_obj=join_expression,
                                              use_labels=True,
                                              whereclause=condition)
            # Create the master join product:
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

        join_product = self.snowflake.join_expression(attributes)
        join_expression = join_product.expression

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
                keys = [level.key for level in hier[0:depth]]
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

        lower = self._boundary_condition(dim, hierarchy, from_path, 0)
        upper = self._boundary_condition(dim, hierarchy, to_path, 1)

        conditions = []
        if lower is not None:
            conditions.append(lower)
        if upper is not None:
            conditions.append(upper)

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

        if self.master_fact is not None:
            ref = self.mapper.physical(attribute, locale)
            self.logger.debug("column %s (%s) from master fact" % (attribute.ref(), ref))
            try:
                return self.master_fact.c[ref.column]
            except KeyError:
                self.logger.debug("retry column %s from tables" % (attribute.ref(), ))
                return self.snowflake.column(attribute, locale)
        else:
            self.logger.debug("column %s from tables" % (attribute.ref(), ))
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
