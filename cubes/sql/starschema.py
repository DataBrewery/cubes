# -*- encoding=utf -*-
"""
cubes.sql.starschema
~~~~~~~~~~~~~~~~~~~~~~~~

Star schema query builder and related structures.

Note: This module is to be remained implemented in a way that it does not use
any of the Cubes objects. It might use duck-typing and assume objects with
similar attributes. No calls to Cubes object functions should be allowed here.

"""

from __future__ import absolute_import


import logging

import sqlalchemy as sa
import sqlalchemy.sql as sql
from collections import namedtuple
from ..errors import InternalError, ModelError, ArgumentError
from .. import compat

# Attribute -> Column
# IF attribute has no 'expression' then mapping is used
# IF attribute has expression, the expression is used and underlying mappings

# TODO: do we need epxression here? We want expression to be on top of
# physically mapped objects
Mapping = namedtuple("StarAttribute",
                     ["schema", "table", "column",
                      # Use only one
                      "extract", "function"])


def to_mapping(obj, default_table=None, default_schema=None):
    """Utility function that will create a `Mapping` object from an anonymous
    tuple, dictionary or a similar object. `obj` can also be a string in form
    ``schema.table.column`` where shcema or both schema and table can be
    ommited. `default_table` and `default_schema` are used when no table or
    schema is provided in `obj`."""

    if obj is None:
        raise ArgumentError("Mapping object can not be None")

    if isinstance(obj, compat.string_type):
        obj = obj.split(".")

    if isinstance(obj, (tuple, list)):
        if len(obj) == 1:
            column = obj[0]
            table = None
            schema = None
        elif len(obj) == 2:
            table, column = obj
            schema = None
        elif len(obj) == 3:
            schema, table, column = obj
        else:
            raise ArgumentError("Join key can have 1 to 3 items"
                                " has {}: {}".format(len(obj), obj))

    elif hasattr(obj, "get"):
        schema = obj.get("schema")
        table = obj.get("table")
        column = obj.get("column")
        extract = obj.get("extract")
        function = obj.get("function")

    else:  # pragma nocover
        schema = obj.schema
        table = obj.table
        extract = obj.extract
        function = obj.function

    table = table or default_table
    schema = schema or default_schema

    return Mapping(schema, table, column, extract, function)


JoinKey = namedtuple("JoinKey",
                     ["schema",
                      "table",
                      "column"])

def to_join_key(obj):
    """Utility function that will create JoinKey tuple from an anonymous
    tuple, dictionary or similar object. `obj` can also be a string in form
    ``schema.table.column`` where schema or both schema and table can be
    ommited."""

    if obj is None:
        return JoinKey(None, None, None)

    if isinstance(obj, compat.string_type):
        obj = obj.split(".")

    if isinstance(obj, (tuple, list)):
        if len(obj) == 1:
            column = obj[0]
            table = None
            schema = None
        elif len(obj) == 2:
            table, column = obj
            schema = None
        elif len(obj) == 3:
            schema, table, column = obj
        else:
            raise ArgumentError("Join key can have 1 to 3 items"
                                " has {}: {}".format(len(obj), obj))

    elif hasattr(obj, "get"):
        schema = obj.get("schema")
        table = obj.get("table")
        column = obj.get("column")

    else:  # pragma nocover
        schema = obj.schema
        table = obj.table
        column = obj.column

    return JoinKey(schema, table, column)

"""Table join specification. `master` and `detail` are TableColumnReference
tuples. `method` denotes which table members should be considered in the join:
*master* – all master members (left outer join), *detail* – all detail members
(right outer join) and *match* – members must match (inner join)."""

Join = namedtuple("Join",
                  ["master", # Master table (fact in star schema)
                   "detail", # Detail table (dimension in star schema)
                   "alias",  # Optional alias for the detail table
                   "method"  # Method how the table is joined
                   ]
                )


def to_join(obj):
    """Utility conversion function that will create `Join` tuple from an
    anonymous tuple, dictionary or similar object."""
    if isinstance(obj, (tuple, list)):
        alias = None
        method = None

        if len(obj) == 3:
            alias = obj[2]
        elif len(obj) == 4:
            alias, method = obj[2], obj[3]
        elif len(obj) < 2 or len(obj) > 4:
            raise ArgumentError("Join object can have 1 to 4 items"
                                " has {}: {}".format(len(obj), obj))

        master = to_join_key(obj[0])
        detail = to_join_key(obj[1])

        return Join(master, detail, alias, method)

    elif hasattr(obj, "get"):  # pragma nocover
        return Join(to_join_key(obj.get("master")),
                    to_join_key(obj.get("detail")),
                    obj.get("alias"),
                    obj.get("method"))

    else:  # pragma nocover
        return Join(to_join_key(obj.master),
                    to_join_key(obj.detail),
                    obj.alias,
                    obj.method)

# Internal table reference
_TableRef = namedtuple("_TableRef",
                       ["schema", # Database schema
                        "name",   # Table name
                        "alias",  # Optional table alias instead of name
                        "key",    # Table key (for caching or referencing)
                        "table",  # SQLAlchemy Table object, reflected
                        "join"    # join which joins this table as a detail
                       ]
                    )

class StarSchemaError(InternalError):
    """Error related to the physical star schema."""
    pass

class NoSuchTableError(StarSchemaError):
    """Error related to the physical star schema."""
    pass

class NoSuchAttributeError(StarSchemaError):
    """Error related to the physical star schema."""
    pass

class StarSchema(object):
    """Represents a star/snowflake table schema. Attributes:

    * `name` – user specific name of the star schema, used for the schema
      identification, debug purposes and logging. Has no effect on the
      execution or statement composition.
    * `metadata` is a SQLAlchemy metadata object where the snowflake tables
      are described.
    * `mappings` is a dictionary of snowflake attributes. The keys are
      attribute names, the values can be strings, dictionaries or objects with
      specific attributes (see below)
    * `fact` is a name or a reference to a fact table
    * `joins` is a list of join specification (see below)
    * `tables` are SQL Alchemy selectables (tables or statements) that are
      referenced in the attributes. This dictionary is looked-up first before
      the actual metadata. Only table name has to be specified and database
      schema should not be used in this case.
    * `schema` – default database schema containing tables

    The columns can be specified as:

    * a string with format: `column`, `table.column` or `schema.table.column`.
      When no table is specified, then the fact table is considered.
    * as a list of arguments `[[schema,] table,] column`
    * `StarColumn` or any object with attributes `schema`, `table`,
      `column`, `extract`, `unary` can be used.
    * a dictionary with keys same as the attributes of `StarColumn` object

    Non-object arguments will be stored as a `StarColumn` objects internally.

    The joins can be specified as a list of:

    * tuples of column specification in form of (`master`, `detail`)
    * a dictionary with keys or object with attributes: `master`, `detail`,
      `alias` and `method`.

    `master` is a specification of a column in the master table (fact) and
    `detail` is a specification of a column in the detail table (usually a
    dimension). `alias` is an alternative name for the `detail` table to be
    joined.

    The `method` can be: `match` – ``LEFT INNER JOIN``, `master` – ``LEFT
    OUTER JOIN`` or `detail` – ``RIGHT OUTER JOIN``.


    Note: It is not in the responsibilities of the `StarSchema` to resolve
    arithmetic expressions neither attribute dependencies. It is up to the
    caller to resolve these and ask for basic columns only.
    """

    def __init__(self, name, metadata, mappings, fact, joins=None,
                 tables=None, schema=None):

        # TODO: expectation is, that the snowlfake is already localized, the
        # owner of the snowflake should generate one snowflake per locale.

        self.name = name
        self.metadata = metadata
        self.mappings = mappings or {}
        self.joins = joins or []
        self.schema = schema
        self.table_expressions = tables or {}

        # Cache
        # -----
        # Keys are logical column labels (keys from `mapping` attribute)
        self._columns = {}
        # Keys are tuples (schema, table)
        self._tables = {}

        self.logger = logging.getLogger("cubes.starschema")

        # TODO: perform JOIN discovery based on foreign keys


        # Fact Table
        # ----------

        # Fact Initialization
        if isinstance(fact, compat.string_type):
            self.fact_name = fact
            self.fact_table = self.physical_table(fact)
        else:
            # We expect fact to be a statement
            self.fact_name = fact.name
            self.fact_table = fact

        # Rest of the initialization
        # --------------------------
        self._collect_tables()

    def _collect_tables(self):
        """Collect and prepare all important information about the tables in
        the schema. The collected information is a list:

        * `table` – SQLAlchemy table or selectable object
        * `schema` – original schema name
        * `name` – original table or selectable object
        * `alias` – alias given to the table or statement
        * `join` – join object that joins the table as a detail to the star

        Input: schema, fact name, fact table, joins
        Output: tables[table_key] = SonwflakeTable()
        """

        # Collect the fact table as the root master table
        #
        fact_table = _TableRef(schema=self.schema,
                               name=self.fact_name,
                               alias=self.fact_name,
                               key=(self.schema, self.fact_name),
                               table=self.fact_table,
                               join=None
                         )

        self._tables[fact_table.key] = fact_table

        # Collect all the detail tables
        # We don't need to collect the master tables as they are expected to
        # be referenced as 'details'. The exception is the fact table that is
        # provided explicitly for the snowflake schema.

        for join in self.joins:
            # just ask for the table

            table = self.physical_table(join.detail.table,
                                        join.detail.schema)

            if join.alias:
                table = table.alias(join.alias)
                alias = join.alias
            else:
                alias = join.detail.table

            key = (join.detail.schema, alias)

            ref = _TableRef(table=table,
                            schema=join.detail.schema,
                            name=join.detail.table,
                            alias=alias,
                            key=key,
                            join=join
                           )

            self._tables[key] = ref

    def table(self, key, role=None):
        """Return a table reference for `key` which has form of a
        tuple (`schema`, `table`). `schema` should be ``None`` for named table
        expressions, which take precedence before the physical tables in the
        default schema. If there is no named table expression then physical
        table is considered.

        The returned object has the following properties:
        * `name` – real table name
        * `alias` – table alias – always contains a value, regardless whether
          the table join provides one or not. If there was no alias provided by
          the join, then the physical table name is used.
        * `key` – table key – the same as the `key` argument
        * `join` – `Join` object that joined the table to the star schema
        * `table` – SQLAlchemy `Table` or table expression object

        `role` is for debugging purposes to display when there is no such
        table, which role of the table was expected, such as master or detail.
        """
        if key is None:
            raise ArgumentError("Table key should not be None")

        try:
            return self._tables[key]
        except KeyError:
            if role:
                for_role = " (as {})".format(role)
            else:
                for_role = ""

            schema = '"{}".'.format(key[0]) if key[0] else ""
            raise StarSchemaError("Unknown star table {}\"{}\"{}"
                                  .format(schema, key[1], for_role))

    def physical_table(self, name, schema=None):
        """Return a physical table or table expression, regardless whether it
        exists or not in the star."""

        # Return a statement or an explicitly craeted table if it exists
        if not schema and name in self.table_expressions:
            return self.table_expressions[name]

        coalesced_schema = schema or self.schema

        try:
            table = sa.Table(name,
                             self.metadata,
                             autoload=True,
                             schema=coalesced_schema)

        except sa.exc.NoSuchTableError:
            in_schema = (" in schema '{}'"
                         .format(schema)) if schema else ""
            msg = "No such fact table '{}'{}.".format(name, in_schema)
            raise NoSuchTableError(msg)

        return table


    def column(self, logical):
        """Return a column for `logical` reference. The returned column will
        have a label same as the `logical`.
        """
        # IMPORTANT:
        #
        # Note to developers: any column that is going to be considered in the
        # result of this method (if composed) MUST be somehow represented in
        # the logical model and MUST be analyzable. For example in custom
        # expressions operating on multiple physical columns all physical
        # columns must be defined as attributes in the cube.
        #
        # Yielding non-represented column might result in undefined behavior
        # (very likely in unvanted cartesian join – one per unknown column)
        #
        # -- END OF IMPORTANT MESSAGE ---

        if logical in self._columns:
            return self._columns[logical]

        try:
            mapping = self.mappings[logical]
        except KeyError:
            raise NoSuchAttributeError(logical)

        key = (mapping.schema or self.schema, mapping.table)

        ref = self.table(key)
        table = ref.table

        try:
            column = table.columns[mapping.column]
        except KeyError:
            avail = ", ".join(str(c) for c in table.columns)
            raise StarSchemaError("Unknown column '%s' in table '%s' possible: %s"
                                  % (mapping.column, mapping.table, avail))

        # Extract part of the date
        if mapping.extract:
            column = sql.expression.extract(mapping.extract, column)
        if mapping.unary:
            # FIXME: add some protection here for the function name!
            column = getattr(sql.expression.func, mapping.unary)(column)

        column = column.label(logical)

        self._columns[logical] = column
        # self._labels[label] = logical

        return column

    def relevant_joins(self, attributes):
        """Get relevant joins to the attributes - list of joins that are
        required to be able to acces specified attributes. `attributes` is a
        list of `StarSchema` attributes (or objects with same kind of
        attributes).
        """

        # Attribute: (schema, table, column)
        # Join: ((schema, table, column), (schema, table, column), alias)

        if not self.joins:
            self.logger.debug("no joins to be searched for")

        # Get the physical mappings for attributes
        mappings = [self.mappings[attr] for attr in attributes]
        # Generate table keys
        required_tables = set((m.schema, m.table) for m in mappings)

        # We assume that the fact table is always present
        fact_table = (self.schema, self.fact_name)

        joined_tables = set()
        joined_tables.add(fact_table)

        joins = []
        # self.logger.debug("tables to join: %s" % list(tables_to_join))

        while required_tables:
            # TODO: check that the detail is not fact table
            detail_key = required_tables.pop()
            detail = self.table(detail_key, "join detail")
            # self.logger.debug("joining table %s" % (table, ))

            join = detail.join

            if not join:
                # We assume this is the fact table
                continue

            joins.append(join)
            # Find master for the detail
            master_key = (join.master.schema, join.master.table)

            if master_key not in self._tables:
                raise StarSchemaError("Unknown master table '%s'" % master_key)

            if master_key not in joined_tables:
                # We are missing the mater, queue it
                required_tables.add(master_key)

        return joins

    # Note: This is "The Method"
    # ==========================

    def star(self, attributes):
        """The main method for generating underlying star schema joins.
        Returns a denormalized JOIN expression that includes all relevant
        tables containing base `attributes` (attributes representing actual
        columns).

        Example use:

        .. code-block:: python

            star = star_schema.star(attributes)
            statement = sql.expression.statement(selection,
                                                 from_obj=star,
                                                 whereclause=condition)
            result = engine.execute(statement)
        """

        # Dictionary of raw tables and their joined products
        # At the end this should contain only one item representing the whole
        # star.
        star = {}

        # Collect all the tables first:
        joins = self.relevant_joins(attributes)

        # There are no joins required for this query
        if not joins:
            # TODO: use core if provided
            return self.fact_table

        # Gather all involved tables
        for join in joins:
            # 1. MASTER
            # Add master table to the list.

            key = (join.master.schema, join.master.table)
            ref = self.table(key)
            star[key] = ref.table

            # 2. DETAIL
            # Add (aliased) detail table to the list. 

            alias = join.alias or join.detail.table
            key = (join.detail.schema, alias)
            ref = self.table(key)
            star[key] = ref.table

        # Here the `star` contains mapping table key -> table, which will be
        # gradually replaced by JOINs

        # Perform the joins
        # =================
        #
        # 1. find the column
        # 2. construct the condition
        # 3. use the appropriate SQL JOIN
        # 
        # TODO: make sure that we have joins in joinable order – that the
        # master is already joined
        # TODO: support MySQL partition (see Issue list)
        for join in joins:
            # Prepare the table keys:
            # Key is a tuple of (schema, table) and is used to get a joined
            # product object
            master = join.master
            master_key = (master.schema, master.table)
            detail = join.detail
            alias = join.alias or join.detail.table
            detail_key = (detail.schema, alias)

            # We need plain tables to get columns for prepare the join
            # condition
            # Master table.column
            # -------------------
            master_table = self.table(master_key).table

            try:
                master_column = master_table.c[master.column]
            except KeyError:
                raise ModelError('Unable to find master key (schema {schema}) '
                                 '"{table}"."{column}" '.format(join.master))

            # Detail table.column
            # -------------------
            detail_table = self.table(detail_key).table

            try:
                detail_column = detail_table.c[detail.column]
            except KeyError:
                raise ModelError('Unable to find detail key (schema {schema}) '
                                 '"{table}"."{column}" '.format(join.detail))

            # The Condition
            # -------------
            onclause = master_column == detail_column

            # Get the joined products – might be plain tables or already
            # joined tables
            try:
                master_table = star[master_key]
            except KeyError:
                raise ModelError("Unknown master %s. Missing join or "
                                 "wrong join order?" % (master_key, ))
            detail_table = star[detail_key]


            # Determine the join type based on the join method. If the method
            # is "detail" then we need to swap the order of the tables
            # (products), because SQLAlchemy provides inteface only for
            # left-outer join.
            if join.method is None or join.method == "match":
                is_outer = False
            elif join.method == "master":
                is_outer = True
            elif join.method == "detail":
                # Swap the master and detail tables to perform RIGHT OUTER JOIN
                master_table, detail_table = (detail_table, master_table)
                is_outer = True
            else:
                raise ModelError("Unknown join method '%s'" % join.method)

            product = sql.expression.join(master_table, detail_table,
                                          onclause=onclause, isouter=is_outer)

            # Replace the already joined master
            del star[detail_key]
            star[master_key] = product

        if not star:  # pragma nocover
            # This should not happen
            raise InternalError("Star is emtpy")

        if len(star) > 1:
            raise ModelError("Some tables are let unjoined: %s"
                             % (star.keys(), ))

        # Return the star – the only remaining join object
        result = list(star.values())[0]

        return result

