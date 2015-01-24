# -*- encoding=utf -*-

from __future__ import absolute_import

import datetime
import re

from collections import namedtuple, OrderedDict

from ...browser import Drilldown, Cell, PointCut, SetCut, RangeCut
from ...browser import SPLIT_DIMENSION_NAME
from ...model import Attribute
from ...errors import *
from ...expr import evaluate_expression
from ...logging import get_logger
from ... import compat

from .mapper import DEFAULT_KEY_FIELD, PhysicalAttribute
from .utils import condition_conjunction, order_column


try:
    import sqlalchemy
    import sqlalchemy.sql as sql

except ImportError:
    from ...common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")


__all__ = [
        "SnowflakeSchema",
        "QueryBuilder"
        ]


SnowflakeAttribute = namedtuple("SnowflakeAttribute", ["attribute", "join"])


"""Product of join_expression"""
JoinedProduct = namedtuple("JoinedProduct",
        ["expression", "tables"])


_SQL_EXPR_CONTEXT = {
    "sqlalchemy": sqlalchemy,
    "sql": sql,
    "func": sql.expression.func,
    "case": sql.expression.case,
    "text": sql.expression.text,
    "datetime": datetime,
    "re": re,
    "extract": sql.expression.extract,
    "and_": sql.expression.and_,
    "or_": sql.expression.or_
}

def table_str(key):
    """Make (`schema`, `table`) tuple printable."""
    table, schema = key
    return "%s.%s" % (str(schema), (table)) if schema else str(table)


MATCH_MASTER_RSHIP = 1
OUTER_DETAIL_RSHIP = 2

class SnowflakeTable(object):
    def __init__(self, schema, name, alias=None, table=None, join=None):
        self.schema = schema
        self.name = name
        self.table = table
        self.alias = alias
        self.join = join
        self.detail_keys = set()

    @property
    def key(self):
        return (self.schema, self.aliased_name)

    @property
    def aliased_name(self):
        return self.alias or self.name

    def __str__(self):
        return "%s.%s" % (self.key)

# TODO: merge this with mapper
class SnowflakeSchema(object):
    def __init__(self, cube, mapper, metadata, safe_labels):
        self.cube = cube
        self.mapper = mapper
        self.metadata = metadata
        self.safe_labels = safe_labels

        # Initialize the shema information: tables, column maps, ...
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

        try:
            self.fact_key_column = self.fact_table.c[self.fact_key].label(self.fact_key)
        except KeyError:
            try:
                self.fact_key_column = list(self.fact_table.columns)[0]
            except Exception as e:
                raise ModelError("Unable to get key column for fact "
                                 "table '%s' in cube '%s'. Reason: %s"
                                 % (self.fact_name, self.cube.name, str(e)))

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
        self._analyse_table_relationships()

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

        Input: schema, fact name, fact table, joins

        Output: tables[table_key] = SonwflakeTable()

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

        # Collect detail keys:
        # 
        # Every table object has a set of keys `detail_keys` which are
        # columns that are used to join detail tables.
        #
        for join in self.mapper.joins:
            key = (join.master.schema, join.master.table)
            try:
                master = self.tables[key]
            except KeyError:
                raise ModelError("Unknown table (or join alias) '%s'"
                                 % table_str(key))
            master.detail_keys.add(join.master.column)

    def _analyse_table_relationships(self):

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
                self.fact_relationships[table] = None

            # Add (aliased) detail table to the rist
            table = (join.detail.schema, join.alias or join.detail.table)
            if table not in relationships:
                relationships[table] = None
            else:
                raise ModelError("Joining detail table %s twice" % (table, ))

        # Analyse the joins
        for join in reversed(self.mapper.joins):
            master_key = (join.master.schema, join.master.table)
            detail_key = (join.detail.schema, join.alias or join.detail.table)

            if relationships.get(detail_key):
                raise InternalError("Detail %s already classified" % detail_key)

            master_rs = relationships[master_key]

            if master_rs is None:
                raise InternalError("Joining to unclassified master. %s->%s "
                                    "Hint: check your joins, their order or "
                                    "mappings." % (table_str(master_key),
                                                   table_str(detail_key)))
            elif master_rs == MATCH_MASTER_RSHIP \
                    and join.method in ("match", "master"):
                relationship = MATCH_MASTER_RSHIP
            elif master_rs == OUTER_DETAIL_RSHIP \
                    or join.method == "detail":
                relationship = OUTER_DETAIL_RSHIP
            else:
                raise InternalError("Unknown relationship combination for "
                                    "%s(%s)->%s(%s)"
                                    % (table_str(master_key), master_rs,
                                       table_str(detail_key), join.method))

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
            try:
                table_ref = tables[attribute]
            except KeyError:
                raise ModelError("Unknown table for attribute %s. "
                                 "Missing mapping?" % attribute)
            try:
                mapping[attribute] = relationships[table_ref]
            except KeyError:
                attr, table = table_ref
                if table:
                    message = "Missing join for table '%s'?" % table
                else:
                    message = "Missing mapping or join?"

                raise ModelError("Can not determine to-fact relationship for "
                                 "attribute '%s'. %s"
                                 % (attribute.ref(), message))
        self.fact_relationships = mapping

        attributes = self.cube.get_attributes(aggregated=True)
        tables = self.mapper.tables_for_attributes(attributes)
        tables = dict(zip(attributes, tables))
        mapping = {}
        for attribute in attributes:
            mapping[attribute] = relationships[tables[attribute]]
        self.aggregated_fact_relationships = mapping

    def _collect_detail_keys(self):
        """Assign to each table which keys from the table are used by another
        detail table as master keys."""


    def is_outer_detail(self, attribute, for_aggregation=False):
        """Returns `True` if the attribute belongs to an outer-detail table."""
        if for_aggregation:
            lookup = self.aggregated_fact_relationships
        else:
            lookup = self.fact_relationships

        try:
            return lookup[attribute] == OUTER_DETAIL_RSHIP
        except KeyError:
            # Retry as raw table (used by internally generated attributes)
            ref = self.mapper.physical(attribute)
            key = (ref.schema, ref.table)
            return self.tables[key].relationship
        except KeyError:
            raise InternalError("No fact relationship for attribute %s "
                                "(aggregate: %s)"
                                % (attribute.ref(), for_aggregation))

    def join_expression(self, attributes, include_fact=True, master_fact=None,
                        master_detail_keys=None):
        """Create partial expression on a fact table with `joins` that can be
        used as core for a SELECT statement. `join` is a list of joins
        returned from mapper (most probably by `Mapper.relevant_joins()`)

        Returns a tuple: (`expression`, `tables`) where `expression` is
        QLAlchemy expression object and `tables` is a list of `SnowflakeTable`
        objects used in the join.

        If `include_fact` is ``True`` (default) then fact table is considered
        as starting point. If it is ``False`` The first detail table is
        considered as starting point for joins. This might be useful when
        getting values of a dimension without cell restrictions.

        `master_fact` is used for building a composed aggregated expression.
        `master_detail_keys` is a dictionary of aliased keys from the master
        fact exposed to the details.

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

        master_detail_keys = master_detail_keys or {}

        tables = []

        fact_key = (self.schema, self.fact_name)

        if include_fact:
            if master_fact is not None:
                fact = master_fact
            else:
                fact = self.fact_table

            joined_products[fact_key] = fact
            tables.append(self.tables[fact_key])

        # Collect all the tables first:
        for join in joins:
            if not join.detail.table or (join.detail.table == self.fact_name and not join.alias):
                raise MappingError("Detail table name should be present and "
                                   "should not be a fact table unless aliased.")

            # 1. MASTER
            # Add master table to the list. If fact table (or statement) was
            # explicitly specified, use it instead of the original fact table

            if master_fact is not None and (join.master.schema, join.master.table) == fact_key:
                table = master_fact
            else:
                table = self.table(join.master.schema, join.master.table)
            joined_products[(join.master.schema, join.master.table)] = table

            # 2. DETAIL
            # Add (aliased) detail table to the rist. Add the detail to the
            # list of joined tables – will be used to determine "outlets" for
            # keys of outer detail joins

            table = self.table(join.detail.schema, join.alias or join.detail.table)
            key = (join.detail.schema, join.alias or join.detail.table)
            joined_products[key] = table
            tables.append(self.tables[key])

        # Perform the joins
        # =================
        #
        # 1. find the column
        # 2. construct the condition
        # 3. use the appropriate SQL JOIN
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
            # TODO: this is unreadable
            if master_fact is not None and (join.master.schema, join.master.table) == fact_key:
                key = (join.master.schema, join.master.table, join.master.column)
                try:
                   master_label = master_detail_keys[key]
                except KeyError:
                    raise InternalError("Missing fact column %s (has: %s)"
                                        % (key, master_detail_keys.keys()))
                master_column = master_fact.c[master_label]
            else:
                master_table = self.table(master.schema, master.table)

                try:
                    master_column = master_table.c[master.column]
                except KeyError:
                    raise ModelError('Unable to find master key (schema %s) '
                                     '"%s"."%s" ' % join.master[0:3])

            detail_table = self.table(join.detail.schema, join.alias or join.detail.table)
            try:
                detail_column = detail_table.c[detail.column]
            except KeyError:
                raise MappingError('Unable to find detail key (schema %s) "%s"."%s" ' \
                                    % join.detail[0:3])

            # The join condition:
            onclause = master_column == detail_column

            # Get the joined products – might be plain tables or already
            # joined tables
            try:
                master_table = joined_products[master_key]
            except KeyError:
                raise ModelError("Unknown master %s. Missing join or "
                                 "wrong join order?" % (master_key, ))
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
        result = list(joined_products.values())[0]

        return JoinedProduct(result, tables)

    def column(self, attribute, locale=None):
        """Return a column object for attribute.

        `locale` is explicit locale to be used. If not specified, then the
        current locale is used for localizable attributes.
        """

        logical = self.mapper.logical(attribute, locale)
        if logical in self.logical_to_column:
            return self.logical_to_column[logical]

        ref = self.mapper.physical(attribute, locale)
        table = self.table(ref.schema, ref.table)

        try:
            column = table.c[ref.column]
        except:
            avail = [str(c) for c in table.columns]
            raise BrowserError("Unknown column '%s' in table '%s' avail: %s"
                               % (ref.column, ref.table, avail))

        # Extract part of the date
        if ref.extract:
            column = sql.expression.extract(ref.extract, column)
        if ref.func:
            column = getattr(sql.expression.func, ref.func)(column)
        if ref.expr:
            # Provide columns for attributes (according to current state of
            # the query)
            context = dict(_SQL_EXPR_CONTEXT)
            getter = _TableGetter(self)
            context["table"] = getter
            getter = _AttributeGetter(self, attribute.dimension)
            context["dim"] = getter
            getter = _AttributeGetter(self, self.cube)
            context["fact"] = getter
            context["column"] = column


            column = evaluate_expression(ref.expr, context, 'expr', sql.expression.ColumnElement)

        if self.safe_labels:
            label = "a%d" % self.label_counter
            self.label_counter += 1
        else:
            label = logical

        if isinstance(column, compat.string_type):
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


class _StatementConfiguration(object):
    def __init__(self):
        self.attributes = []
        self.cuts = []
        self.cut_attributes = []
        self.other_attributes = []

        self.split_attributes = []
        self.split_cuts = []

        self.ptd_attributes = []

    @property
    def all_attributes(self):
        """All attributes that should be considered for a statement
        composition.  Mostly used to get the relevant joins."""

        return set(self.attributes) | set(self.cut_attributes) \
                | set(self.split_attributes) | set(self.other_attributes)

    def merge(self, other):
        self.attributes += other.attributes
        self.cuts += other.cuts
        self.cut_attributes += other.cut_attributes

        self.split_attributes += other.split_attributes
        self.split_cuts += other.split_cuts

        self.other_attributes += other.other_attributes
        self.ptd_attributes += other.ptd_attributes

    def is_empty(self):
        return not (bool(self.attributes) \
                    or bool(self.cut_attributes) \
                    or bool(self.other_attributes) \
                    or bool(self.split_attributes))

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

        # Semi-additive dimension
        # TODO: move this to model (this is ported from the original
        # SnapshotBrowser)

        # TODO: remove this later
        if "semiadditive" in self.cube.info:
            raise NotImplementedError("'semiadditive' in 'info' is not "
                                      "supported any more")

        for dim in self.cube.dimensions:
            if dim.nonadditive:
                raise NotImplementedError("Non-additive behavior for "
                                          "dimensions is not yet implemented."
                                          "(cube '%s', dimension '%s')" %
                                          (self.cube.name, dim.name))

    def aggregation_statement(self, cell, drilldown=None, aggregates=None,
                              split=None, attributes=None, summary_only=False):
        """Builds a statement to aggregate the `cell`.

        * `cell` – `Cell` to aggregate
        * `drilldown` – a `Drilldown` object
        * `aggregates` – list of aggregates to consider
        * `split` – split cell for split condition
        * `summary_only` – do not perform GROUP BY for the drilldown. The
        * drilldown is used only for choosing tables to join and affects outer
          detail joins in the result

        Algorithm description:

        All the tables have one of the two relationship to the fact:
        *master/match* or *detail*. Every table connected to a table that has
        "detail" relationship is considered also in the "detail" relationship
        towards the fact. Therefore we have two join zones: all master or
        detail tables from the core, directly connected to the fact table and
        rest of the table connected to the core through outer detail
        relationship.

        Depending on the query it is decided whether we are fine with just
        joining everything together into single join or we need to separate
        the fact master core from the outer details::

                        +------+           +-----+
                        | fact |--(match)--| dim +
                        +------+           +-----+
            Master Fact    |
            ===============|========================
            Outer Details  |               +-----+
                           +------(detail)-| dim |
                                           +-----+

        The outer details part is RIGHT OUTER JOINed to the fact. Since there
        are no tables any more, the original table keys for joins to the outer
        details were exposed and specially labeled as `__masterkeyXX` where XX
        is a sequence number of the key. The `join_expression` JOIN
        constructing method receives the map of the keys and replaces the
        original tables with connections to the columns already selected in
        the master fact.

        .. note::

            **Limitation:** we can not have a Cut (condition) where keys (path
            elements) are from both join zones. Whole cut should be within one
            zone: either the master fact or outer details.
        """

        if not aggregates:
            raise ArgumentError("List of aggregates sohuld not be empty")

        drilldown = drilldown or Drilldown()

        # Configuraion of statement parts
        master = _StatementConfiguration()
        detail = _StatementConfiguration()

        self.logger.debug("prepare aggregation statement. cell: '%s' "
                          "drilldown: '%s' summary only: %s" %
                          (",".join([str(cut) for cut in cell.cuts]),
                          drilldown, summary_only))

        # Analyse and Prepare
        # -------------------
        # Get the cell attributes and find whether we have some outer details
        #
        # Cut
        # ~~~

        mcuts, mattrs, dcuts, dattrs = self._split_cell_by_relationship(cell)
        master.cuts += mcuts
        master.cut_attributes += mattrs
        detail.cuts += dcuts
        detail.cut_attributes += dattrs

        # Split
        # ~~~~~
        # Same as Cut, just different target

        mcuts, mattrs, dcuts, dattrs = self._split_cell_by_relationship(split)
        master.split_cuts += mcuts
        master.split_attributes += mattrs
        detail.split_cuts += dcuts
        detail.split_attributes += dattrs

        # Drilldown
        # ~~~~~~~~~

        drilldown_attributes = drilldown.all_attributes()
        master.attributes, detail.attributes = \
                self._split_attributes_by_relationship(drilldown_attributes)

        # Period-to-date
        #
        # One thing we have to do later is to generate the PTD condition
        # (either for master or for detail) and assign it to the appropriate
        # list of conditions

        ptd_attributes = self._ptd_attributes(cell, drilldown)
        ptd_master, ptd_detail = self._split_attributes_by_relationship(ptd_attributes)
        if ptd_master and ptd_detail:
            raise InternalError("PTD attributes are spreading from master "
                                "to outer detail. This is not supported.")
        elif ptd_master:
            master.ptd_attributes = ptd_master
        elif ptd_detail:
            detail.ptd_attributes = ptd_detail

        # TODO: PTD workaround #2
        # We need to know which attributes have to be included for JOINs,
        # however we can know this only when "condition" in mapping is
        # evaluated, which can be evaluated only after joins and when the
        # master-fact is ready.
        required = self.cube.browser_options.get("ptd_master_required", [])

        if required:
            required = self.cube.get_attributes(required)
            master.ptd_attributes += required

        # Semi-additive attribute
        semiadditives = self.semiadditive_attributes(aggregates, drilldown)
        sa_master, sa_detail = self._split_attributes_by_relationship(semiadditives)
        master.other_attributes += sa_master
        detail.other_attributes += sa_detail

        # Pick the method:
        #
        # M - master, D - detail
        # C - condition, A - selection attributes (drilldown)
        #
        #    MA MC DA DC | method
        #    ============|=======
        #  0 -- -- -- -- | simple
        #  1 xx -- -- -- | simple
        #  2 -- xx -- -- | simple
        #  3 xx xx -- -- | simple
        #  4 -- -- xx -- | simple
        #  5 xx -- xx -- | simple
        #  6 -- xx xx -- | composed
        #  7 xx xx xx -- | composed
        #  8 -- -- -- xx | simple
        #  9 xx -- -- xx | simple
        # 10 -- -- xx xx | simple
        # 11 xx -- xx xx | simple
        # 12 -- xx -- xx | composed
        # 13 xx xx -- xx | composed
        # 14 -- xx xx xx | composed
        # 15 xx xx xx xx | composed
        # 

        # The master cut is in conflict with detail drilldown or detail cut 
        if master.cut_attributes and (detail.attributes or
                                        detail.cut_attributes):
            simple_method = False
        else:
            simple_method = True
            master.merge(detail)

        coalesce_measures = not detail.is_empty()

        master_conditions = self.conditions_for_cuts(master.cuts)

        if simple_method:
            self.logger.debug("statement: simple")

            # Drilldown – Group-by
            # --------------------
            #
            # SELECT – Prepare the master selection
            #     * master drilldown items

            selection = [self.column(a) for a in set(master.attributes)]
            group_by = selection[:]

            # SPLIT
            # -----
            if split:
                master_split = self._cell_split_column(master.split_cuts)
                group_by.append(master_split)
                selection.append(master_split)

            # WHERE
            # -----
            conditions = master_conditions
            ptd_attributes = master.ptd_attributes

            # JOIN
            # ----
            attributes = set(aggregates) \
                            | master.all_attributes \
                            | set(ptd_attributes)
            join = self.snowflake.join_expression(attributes)
            join_expression = join.expression

        else:
            self.logger.debug("statement: composed")

            # 1. MASTER FACT
            # ==============

            join = self.snowflake.join_expression(master.all_attributes)
            join_expression = join.expression

            # Store a map of joined columns for later
            # The map is: (schema, table, column) -> column

            # Expose fact master detail key outlets:
            master_detail_keys = {}
            master_detail_selection = []
            counter = 0
            for table in join.tables:
                for key in table.detail_keys:
                    column_key = (table.schema, table.aliased_name, key)
                    label = "__masterkey%d" % counter
                    master_detail_keys[column_key] = label

                    column = table.table.c[key].label(label)
                    master_detail_selection.append(column)
                    counter += 1

            # SELECT – Prepare the master selection
            #     * drilldown items
            #     * measures
            #     * aliased keys for outer detail joins

            # Note: Master selection is carried as first (we need to retrieve
            # it later by index)
            master_selection = [self.column(a) for a in set(master.attributes)]

            measures = self.measures_for_aggregates(aggregates)
            measure_selection = [self.column(m) for m in measures]

            selection = master_selection \
                            + measure_selection \
                            + master_detail_selection

            # SPLIT
            # -----
            if master.split_cuts:
                master_split = self._cell_split_column(master.split_cuts,
                                                       "__master_split")
                group_by.append(master_split)
                selection.append(master_split)
            else:
                master_split = None

            # Add the fact key – to properely handle COUNT()
            selection.append(self.snowflake.fact_key_column)

            # WHERE Condition
            # ---------------
            condition = condition_conjunction(master_conditions)

            # Add the PTD
            if master.ptd_attributes:
                ptd_condition = self._ptd_condition(master.ptd_attributes)
                condition = condition_conjunction([condition, ptd_condition])
                # TODO: PTD workaround #3:
                # Add the PTD attributes to the selection,so the detail part
                # of the join will be able to find them in the master
                cols = [self.column(a) for a in master.ptd_attributes]
                selection += cols

            # Prepare the master_fact statement:
            statement = sql.expression.select(selection,
                                              from_obj=join_expression,
                                              use_labels=True,
                                              whereclause=condition)

            # From now-on the self.column() method will return columns from
            # master_fact if applicable.
            self.master_fact = statement.alias("__master_fact")

            # Add drilldown – Group-by
            # ------------------------
            #

            # SELECT – Prepare the detail selection
            #     * master drilldown items (inherit)
            #     * detail drilldown items

            master_cols = list(self.master_fact.columns)
            master_selection = master_cols[0:len(master.attributes)]

            detail_selection = [self.column(a) for a in set(detail.attributes)]

            selection = master_selection + detail_selection
            group_by = selection[:]

            # SPLIT
            # -----
            if detail.split_cuts:
                if master_split:
                    # Merge the detail and master part of the split "dimension"
                    master_split = self.master_fact.c["__master_split"]
                    detail_split = self._cell_split_column(detail.split_cuts,
                                        "__detail_split")
                    split_condition = (master_split and detail_split)
                    detail_split = sql.expression.case([(split_condition, True)],
                                                       else_=False)
                    detail_split.label(SPLIT_DIMENSION_NAME)
                else:
                    # We have only detail split, no need to merge the
                    # condition
                    detail_split = self._cell_split_column(detail.split_cuts)

                selection.append(detail_split)
                group_by.append(detail_split)


            # WHERE
            # -----
            conditions = self.conditions_for_cuts(detail.cuts)
            ptd_attributes = detail.ptd_attributes

            # JOIN
            # ----
            # Replace the master-relationship tables with single master fact
            # Provide mapping between original table columns to the master
            # fact selection (with labelled columns)
            join = self.snowflake.join_expression(detail.all_attributes,
                                                  master_fact=self.master_fact,
                                                  master_detail_keys=master_detail_keys)

            join_expression = join.expression

        # The Final Statement
        # ===================
        #

        # WHERE
        # -----
        if ptd_attributes:
            ptd_condition = self._ptd_condition(ptd_attributes)
            self.logger.debug("adding PTD condition: %s" % str(ptd_condition))
            conditions.append(ptd_condition)

        condition = condition_conjunction(conditions)
        group_by = group_by if not summary_only else None

        # Include the semi-additive dimension, if required
        #
        if semiadditives:
            self.logger.debug("preparing semiadditive subquery for "
                              "attributes: %s"
                              % [a.name for a in semiadditives])

            join_expression = self._semiadditive_subquery(semiadditives,
                                                     selection,
                                                     from_obj=join_expression,
                                                     condition=condition,
                                                     group_by=group_by)

        aggregate_selection = self.builtin_aggregate_expressions(aggregates,
                                                       coalesce_measures=coalesce_measures)

        if summary_only:
            # Don't include the group-by part (see issue #157 for more
            # information)
            selection = aggregate_selection
        else:
            selection += aggregate_selection

        # condition = None
        statement = sql.expression.select(selection,
                                          from_obj=join_expression,
                                          use_labels=True,
                                          whereclause=condition,
                                          group_by=group_by)

        self.statement = statement
        self.labels = self.snowflake.logical_labels(selection)

        # Used in order
        self.drilldown = drilldown
        self.split = split

        return self.statement

    def _split_attributes_by_relationship(self, attributes):
        """Returns a tuple (`master`, `detail`) where `master` is a list of
        attributes that have master/match relationship towards the fact and
        `detail` is a list of attributes with outer detail relationship
        towards the fact."""

        if not attributes:
            return ([],[])

        master = []
        detail = []
        for attribute in attributes:
            if self.snowflake.is_outer_detail(attribute):
                detail.append(attribute)
            else:
                master.append(attribute)

        return (master, detail)

    def _split_cell_by_relationship(self, cell):
        """Returns a tuple of _StatementConfiguration objects (`master`,
        `detail`)"""

        if not cell:
            return ([], [], [], [])

        master_cuts = []
        master_cut_attributes = []
        detail_cuts = []
        detail_cut_attributes = []

        for cut, attributes in self.attributes_for_cell_cuts(cell):
            is_outer_detail = [self.snowflake.is_outer_detail(a) for a in attributes]

            if all(is_outer_detail):
                detail_cut_attributes += attributes
                detail_cuts.append(cut)
            elif any(is_outer_detail):
                raise InternalError("Cut %s is spreading from master to "
                                    "outer detail is not supported."
                                    % str(cut))
            else:
                master_cut_attributes += attributes
                master_cuts.append(cut)

        return (master_cuts, master_cut_attributes,
                detail_cuts, detail_cut_attributes)

    def _cell_split_column(self, cuts, label=None):
        """Create a column for a cell split from list of `cust`."""

        conditions = self.conditions_for_cuts(cuts)
        condition = condition_conjunction(conditions)
        split_column = sql.expression.case([(condition, True)],
                                           else_=False)

        label = label or SPLIT_DIMENSION_NAME

        return split_column.label(label)

    def semiadditive_attributes(self, aggregates, drilldown):
        """Returns an attribute from a semi-additive dimension, if defined for
        the cube. Cubes allows one semi-additive dimension. """

        nonadds = set(self.cube.nonadditive_type(agg) for agg in aggregates)
        # If there is no nonadditive aggregate, we skip
        if not any(nonaddtype for nonaddtype in nonadds):
            return None

        if None in nonadds:
            nonadds.remove(None)

        if "time" not in nonadds:
            raise NotImplementedError("Nonadditive aggregates for other than "
                                      "time dimension are not supported.")

        # Here we expect to have time-only nonadditive
        # TODO: What to do if we have more?

        # Find first time drill-down, if any
        items = [item for item in drilldown \
                       if item.dimension.role == "time"]

        attributes = []
        for item in drilldown:
            if item.dimension.role != "time":
                continue
            attribute = Attribute("__key__", dimension=item.dimension)
            attributes.append(attribute)

        if not attributes:
            time_dims = [ d for d in self.cube.dimensions if d.role == "time" ]
            if not time_dims:
                raise BrowserError("Cannot locate a time dimension to apply for semiadditive aggregates: %r" % nonadds)
            attribute = Attribute("__key__", dimension=time_dims[0])
            attributes.append(attribute)

        return attributes

    def _semiadditive_subquery(self, attributes, selection,
                               from_obj, condition, group_by):
        """Prepare the semi-additive subquery"""
        sub_selection = selection[:]

        semiadd_selection = []
        for attr in attributes:
            col = self.column(attr)
            # Only one function is supported for now: max()
            func = sql.expression.func.max
            col = func(col)
            semiadd_selection.append(col)

        sub_selection += semiadd_selection

        # This has to be the same as the final SELECT, except the subquery
        # selection
        sub_statement = sql.expression.select(sub_selection,
                                              from_obj=from_obj,
                                              use_labels=True,
                                              whereclause=condition,
                                              group_by=group_by)

        sub_statement = sub_statement.alias("__semiadditive_subquery")

        # Construct the subquery JOIN condition
        # Skipt the last subquery selection which we have created just
        # recently
        join_conditions = []

        for left, right in zip(selection, sub_statement.columns):
            join_conditions.append(left == right)

        remainder = list(sub_statement.columns)[len(selection):]
        for attr, right in zip(attributes, remainder):
            left = self.column(attr)
            join_conditions.append(left == right)

        join_condition = condition_conjunction(join_conditions)
        join_expression = from_obj.join(sub_statement, join_condition)

        return join_expression

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
            attributes = self.cube.all_attributes

        join_attributes = set(attributes) | self.attributes_for_cell(cell)

        join_product = self.snowflake.join_expression(join_attributes)
        join_expression = join_product.expression

        columns = self.snowflake.columns(attributes, expand_locales=expand_locales)

        if include_fact_key:
            columns.insert(0, self.snowflake.fact_key_column)

        if cell is not None:
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

    def members_statement(self, cell, attributes=None):
        """Prepares dimension members statement."""
        self.denormalized_statement(cell, attributes, include_fact_key=False)
        group_by = self.snowflake.columns(attributes)
        self.statement = self.statement.group_by(*group_by)
        return self.statement

    def fact(self, id_):
        """Selects only fact with given id"""
        condition = self.snowflake.fact_key_column == id_
        return self.append_condition(condition)

    def append_condition(self, condition):
        """Appends `condition` to the generated statement."""
        self.statement = self.statement.where(condition)
        return self.statement

    def measures_for_aggregates(self, aggregates):
        """Returns a list of measures for `aggregates`. This method is used in
        constructing the master fact."""

        measures = []

        aggregates = [agg for agg in aggregates if agg.function]

        for aggregate in aggregates:
            function_name = aggregate.function.lower()
            function = self.browser.builtin_function(function_name, aggregate)

            if not function:
                continue

            names = function.required_measures(aggregate)
            if names:
                measures += self.cube.get_attributes(names)

        return measures

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
        """Returns a list of tuples (`cut`, `attributes`) where `attributes`
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
        condition = condition_conjunction(conditions)
        return condition

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

        condition = condition_conjunction(conditions)

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
        condition = condition_conjunction(conditions)

        if last is not None:
            condition = sql.expression.or_(condition, last)

        return condition

    def _ptd_attributes(self, cell, drilldown):
        """Return attributes that are used for the PTD condition. Output of
        this function is used for master/detail fact composition and for the
        `_ptd_condition()`"""
        # Include every level only once
        levels = set()

        # For the cell:
        if cell:
            levels |= set(item[2] for item in cell.deepest_levels())

        # For drilldown:
        if drilldown:
            levels |= set(item[2] for item in drilldown.deepest_levels())

        attributes = []
        for level in levels:
            ref = self.mapper.physical(level.key)
            if ref.condition:
                attributes.append(level.key)

        return attributes

    def _ptd_condition(self, ptd_attributes):
        """Returns "periods to date" condition for `ptd_attributes` (which
        should be a result of `_ptd_attributes()`)"""

        # Collect the conditions
        #
        # Conditions are currently specified in the mappings as "condtition"
        # Collect relevant columns – those with conditions

        # Construct the conditions from the physical attribute expression
        conditions = []

        for attribute in ptd_attributes:
            # FIXME: this is a hack

            ref = self.mapper.physical(attribute)
            if not ref.condition:
                continue

            column = self.column(attribute)

            # Provide columns for attributes (according to current state of
            # the query)
            context = dict(_SQL_EXPR_CONTEXT)
            getter = _TableGetter(self)
            context["table"] = getter
            getter = _AttributeGetter(self, attribute.dimension)
            context["dim"] = getter
            getter = _AttributeGetter(self, self.cube)
            context["fact"] = getter
            context["column"] = column

            condition = evaluate_expression(ref.condition,
                                            context,
                                            'condition',
                                            sql.expression.ColumnElement)

            conditions.append(condition)

        # TODO: What about invert?
        return condition_conjunction(conditions)

    def fact_key_column(self):
        """Returns a column that represents the fact key."""
        # TODO: this is used only in FactCountFunction, suggestion for better
        # solution is in the comments there.
        if self.master_fact is not None:
            return self.master_fact.c[self.snowflake.fact_key]
        else:
            return self.snowflake.fact_key_column

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
                lvl_attr = level.order_attribute or level.key
                lvl_order = level.order or 'asc'
                order.append((lvl_attr, lvl_order))

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



# Used as a workaround for "condition" attribute mapping property
# TODO: temp solution
# Assumption: every other attribute is from the same dimension
class _AttributeGetter(object):
    def __init__(self, owner, context):
        self._context = context
        self._owner = owner

    def __getattr__(self, attr):
        return self._column(attr)

    def __getitem__(self, item):
        return self._column(item)

    def _column(self, name):
        attribute = self._context.attribute(name)
        return self._owner.column(attribute)

    # Backward-compatibility for table.c.foo
    @property
    def c(self):
        return self

class _TableGetter(object):
    def __init__(self, owner):
        self._owner = owner

    def __getattr__(self, attr):
        return self._table(attr)

    def __getitem__(self, item):
        return self._table(item)

    def _table(self, name):
        # Create a dummy attribute
        return _ColumnGetter(self._owner, name)


class _ColumnGetter(object):
    def __init__(self, owner, table):
        self._owner = owner
        self._table = table

    def __getattr__(self, attr):
        return self._column(attr)

    def __getitem__(self, item):
        return self._column(item)

    def _column(self, name):
        # Create a dummy attribute
        attribute = PhysicalAttribute(name, table=self._table)
        return self._owner.column(attribute)

    # Backward-compatibility for table.c.foo
    @property
    def c(self):
        return self

