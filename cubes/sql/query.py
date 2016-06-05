# -*- encoding=utf -*-
"""
cubes.sql.query
~~~~~~~~~~~~~~~

Star/snowflake schema query construction structures

"""

# Note for developers and maintainers
# -----------------------------------
#
# This module is to be remained implemented in a way that it does not use any
# of the Cubes objects. It might use duck-typing and assume objects with
# similar attributes. No calls to Cubes object functions should be allowed
# here.

from __future__ import absolute_import

import logging
from collections import namedtuple

import sqlalchemy as sa
import sqlalchemy.sql as sql
from sqlalchemy.sql.expression import and_

from ..model import object_dict
from ..errors import InternalError, ModelError, ArgumentError, HierarchyError
from .. import compat
from ..browser import SPLIT_DIMENSION_NAME
from ..cells import PointCut, SetCut, RangeCut

from .expressions import compile_attributes


# Default label for all fact keys
FACT_KEY_LABEL = '__fact_key__'

# Attribute -> Column
# IF attribute has no 'expression' then mapping is used
# IF attribute has expression, the expression is used and underlying mappings

"""Physical column (or column expression) reference. `schema` is a database
schema name, `table` is a table (or table expression) name containing the
`column`. `extract` is an element to be extracted from complex data type such
as date or JSON (in postgres). `function` is name of unary function to be
applied on the `column`.

Note that either `extract` or `function` can be used, not both."""

Column = namedtuple("Column", ["schema", "table", "column",
                               "extract", "function"])

#
# IMPORTANT: If you decide to extend the above Mapping functionality by adding
# other mapping attributes (not recommended, but still) or by changing the way
# how existing attributes are used, make sure that there are NO OTHER COLUMNS
# than the `column` used. Every column used MUST be accounted in the
# relevant_joins() call.
#
# See similar comment in the column() method of the StarSchema.
#

def to_column(obj, default_table=None, default_schema=None):
    """Utility function that will create a `Column` reference object from an
    anonymous tuple, dictionary or a similar object. `obj` can also be a
    string in form ``schema.table.column`` where shcema or both schema and
    table can be ommited. `default_table` and `default_schema` are used when
    no table or schema is provided in `obj`.

    .. versionadded:: 1.1
    """

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
        extract = None
        function = None

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

    return Column(schema, table, column, extract, function)


# TODO: remove this and use just Column
JoinKey = namedtuple("JoinKey",
                     ["schema",
                      "table",
                      "column"])


def to_join_key(obj):
    """Utility function that will create JoinKey tuple from an anonymous
    tuple, dictionary or similar object. `obj` can also be a string in form
    ``schema.table.column`` where schema or both schema and table can be
    ommited. Dictionary representation of a join key has values: ``schema``,
    ``table`` and ``column``. With the dicitonary representation, the
    ``column`` can be a list of columns in the same table. Both master and
    detail joins have to have the same number of columns in the join key.

    Note that Cubes at this low level does not know which table is used for a
    dimension, therefore the default dimension schema from mapper's naming can
    not be assumed here and has to be explicitly mentioned.

    .. versionadded:: 1.1
    """


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

    # Make it immutable and hashable, as the whole Join object has to be
    # hashable
    if isinstance(column, list):
        column = tuple(column)

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
    anonymous tuple, dictionary or similar object.

    .. versionadded:: 1.1
    """

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


class SchemaError(InternalError):
    """Error related to the physical star schema."""
    pass


class NoSuchTableError(SchemaError):
    """Error related to the physical star schema."""
    pass


class NoSuchAttributeError(SchemaError):
    """Error related to the physical star schema."""
    pass


def _format_key(key):
    """Format table key `key` to a string."""
    schema, table = key

    table = table or "(FACT)"

    if schema:
        return "{}.{}".format(schema, table)
    else:
        return table


def _make_compound_key(table, key):
    """Returns a list of columns from `column_key` for `table` representing
    potentially a compound key. The `column_key` can be a name of a single
    column or list of column names."""

    if not isinstance(key, (list, tuple)):
        key = [key]

    return [table.columns[name] for name in key]


class StarSchema(object):
    """Represents a star/snowflake table schema. Attributes:

    * `label` – user specific label for the star schema, used for the schema
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
      `column`, `extract`, `function` can be used.
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


    .. note::

        The `tables` statements need to be aliased.

    .. versionadded:: 1.1
    """

    def __init__(self, label, metadata, mappings, fact, fact_key='id',
                 joins=None, tables=None, schema=None):

        # TODO: expectation is, that the snowlfake is already localized, the
        # owner of the snowflake should generate one snowflake per locale.
        # TODO: use `facts` instead of `fact`

        if fact is None:
            raise ArgumentError("Fact table or table name not specified "
                                "for star/snowflake schema {}"
                                .format(label))

        self.label = label
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
            try:
                self.fact_name = fact.name
            except AttributeError:
                raise ArgumentError("Fact table statement requires alias()")

            self.fact_table = fact

        self.fact_key = fact_key

        # Try to get the fact key, if does not exist, then consider the first
        # table column as the fact key.
        try:
            self.fact_key_column = self.fact_table.columns[self.fact_key]
        except KeyError:
            try:
                self.fact_key_column = list(self.fact_table.columns)[0]
            except Exception as e:
                raise ModelError("Unable to get key column for fact "
                                 "table '%s' in '%s'. Reason: %s"
                                 % (self.fact_name, label, str(e)))
            else:
                self.fact_key = self.fact_key_column.name

        self.fact_key_column = self.fact_key_column.label(FACT_KEY_LABEL)

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


        # Collect details for duplicate verification. It sohuld not be
        # possible to join one detail multiple times with the same name. Alias
        # has to be used.
        details = set()

        for join in self.joins:
            # just ask for the table

            if not join.detail.table:
                raise ModelError("No detail table specified for a join in "
                                 "schema '{}'. Master of the join is '{}'"
                                 .format(self.label,
                                         _format_key(self._master_key(join))))

            table = self.physical_table(join.detail.table,
                                        join.detail.schema)

            if join.alias:
                table = table.alias(join.alias)
                alias = join.alias
            else:
                alias = join.detail.table

            key = (join.detail.schema or self.schema, alias)

            if key in details:
                raise ModelError("Detail table '{}' joined twice in star"
                                 " schema {}. Join alias is required."
                                 .format(_format_key(key), self.label))
            details.add(key)

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

        key = (key[0] or self.schema, key[1] or self.fact_name)

        try:
            return self._tables[key]
        except KeyError:
            if role:
                for_role = " (as {})".format(role)
            else:
                for_role = ""

            schema = '"{}".'.format(key[0]) if key[0] else ""

            raise SchemaError("Unknown star table {}\"{}\"{}. Missing join?"
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
        # IMPORTANT
        #
        # Note to developers: any column returned from this method
        # MUST be somehow represented in the logical model and MUST be
        # accounted in the relevant_joins(). For example in custom expressions
        # operating on multiple physical columns all physical
        # columns must be defined at the higher level attributes objects in
        # the cube. This is to access the very base column, that has physical
        # representation in a table or a table-like statement.
        #
        # Yielding non-represented column might result in undefined behavior,
        # very likely in unwanted cartesian join – one per unaccounted column.
        #
        # -- END OF IMPORTANT MESSAGE ---

        if logical in self._columns:
            return self._columns[logical]

        try:
            mapping = self.mappings[logical]
        except KeyError:
            if logical == FACT_KEY_LABEL:
                return self.fact_key_column
            else:
                raise NoSuchAttributeError(logical)

        key = (mapping.schema or self.schema, mapping.table or self.fact_name)

        ref = self.table(key)
        table = ref.table

        try:
            column = table.columns[mapping.column]
        except KeyError:
            avail = ", ".join(str(c) for c in table.columns)
            raise SchemaError("Unknown column '%s' in table '%s' possible: %s"
                              % (mapping.column, mapping.table, avail))

        # Extract part of the date
        if mapping.extract:
            column = sql.expression.extract(mapping.extract, column)
        if mapping.function:
            # FIXME: add some protection here for the function name!
            column = getattr(sql.expression.func, mapping.function)(column)

        column = column.label(logical)

        self._columns[logical] = column

        return column

    def _master_key(self, join):
        """Generate join master key, use schema defaults"""
        return (join.master.schema or self.schema,
                join.master.table or self.fact_name)

    def _detail_key(self, join):
        """Generate join detail key, use schema defaults"""
        # Note: we don't include fact as detail table by default. Fact can not
        # be detail (at least for now, we don't have a case where it could be)
        return (join.detail.schema or self.schema,
                join.alias or join.detail.table)

    def required_tables(self, attributes):
        """Get all tables that are required to be joined to get `attributes`.
        `attributes` is a list of `StarSchema` attributes (or objects with
        same kind of attributes).
        """

        # Attribute: (schema, table, column)
        # Join: ((schema, table, column), (schema, table, column), alias)

        if not self.joins:
            self.logger.debug("no joins to be searched for")

        # Get the physical mappings for attributes
        mappings = [self.mappings[attr] for attr in attributes]

        # Generate table keys
        relevant = set(self.table((m.schema, m.table)) for m in mappings)

        # Dependencies
        # ------------
        # `required` now contains tables that contain requested `attributes`.
        # Nowe we have to resolve all dependencies.

        required = {}
        while relevant:
            table = relevant.pop()
            required[table.key] = table

            if not table.join:
                continue

            master = self._master_key(table.join)
            if master not in required:
                relevant.add(self.table(master))

            detail = self._detail_key(table.join)
            if detail not in required:
                relevant.add(self.table(detail))

        # Sort the tables
        # ---------------

        fact_key = (self.schema, self.fact_name)
        fact = self.table(fact_key, "fact master")
        masters = {fact_key: fact}

        sorted_tables = [fact]

        while required:
            details = [table for table in required.values()
                       if table.join
                       and self._master_key(table.join) in masters]

            if not details:
                break

            for detail in details:
                masters[detail.key] = detail
                sorted_tables.append(detail)

                del required[detail.key]

        if len(required) > 1:
            keys = [_format_key(table.key)
                    for table in required.values()
                    if table.key != fact_key]

            raise ModelError("Some tables are not joined: {}"
                             .format(", ".join(keys)))

        return sorted_tables

    # Note: This is "The Method"
    # ==========================

    def get_star(self, attributes):
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

        attributes = [str(attr) for attr in attributes]
        # Collect all the tables first:
        tables = self.required_tables(attributes)

        # Dictionary of raw tables and their joined products
        # At the end this should contain only one item representing the whole
        # star.
        star_tables = {table_ref.key:table_ref.table for table_ref in tables}

        # Here the `star` contains mapping table key -> table, which will be
        # gradually replaced by JOINs

        # Perform the joins
        # =================
        #
        # 1. find the column
        # 2. construct the condition
        # 3. use the appropriate SQL JOIN
        # 4. wrap the star with detail
        # 
        # TODO: support MySQL partition (see Issue list)

        # First table does not need to be joined. It is the "fact" (or other
        # central table) of the schema.
        star = tables[0].table

        for table in tables[1:]:
            if not table.join:
                raise ModelError("Missing join for table '{}'"
                                 .format(_format_key(table.key)))

            join = table.join

            # Get the physical table object (aliased) and already constructed
            # key (properly aliased)
            detail_table = table.table
            detail_key = table.key

            # The `table` here is a detail table to be joined. We need to get
            # the master table this table joins to:

            master = join.master
            master_key = self._master_key(join)

            # We need plain tables to get columns for prepare the join
            # condition. We can't get it form `star`.
            # Master table.column
            # -------------------
            master_table = self.table(master_key).table

            try:
                master_columns = _make_compound_key(master_table,
                                                    master.column)
            except KeyError as e:
                raise ModelError('Unable to find master key column "{key}" '
                                 'in table "{table}" for star {schema} '
                                 .format(schema=self.label,
                                         key=e,
                                         table=_format_key(master_key)))

            # Detail table.column
            # -------------------
            try:
                detail_columns = _make_compound_key(detail_table,
                                                    join.detail.column)
            except KeyError as e:
                raise ModelError('Unable to find detail key column "{key}" '
                                 'in table "{table}" for star {schema} '
                                 .format(schema=self.label,
                                         key=e,
                                         table=_format_key(detail_key)))

            if len(master_columns) != len(detail_columns):
                raise ModelError("Compound keys for master '{}' and detail "
                                 "'{}' table in star {} have different number"
                                 " of columns"
                                 .format(_format_key(master_key),
                                         _format_key(detail_key),
                                         self.label))

            # The JOIN ON condition
            # ---------------------
            key_conditions = [left == right
                              for left, right
                              in zip(master_columns, detail_columns)]
            onclause = and_(*key_conditions)

            # Determine the join type based on the join method. If the method
            # is "detail" then we need to swap the order of the tables
            # (products), because SQLAlchemy provides inteface only for
            # left-outer join.
            left, right = (star, detail_table)

            if join.method is None or join.method == "match":
                is_outer = False
            elif join.method == "master":
                is_outer = True
            elif join.method == "detail":
                # Swap the master and detail tables to perform RIGHT OUTER JOIN
                left, right = (right, left)
                is_outer = True
            else:
                raise ModelError("Unknown join method '%s'" % join.method)

            star = sql.expression.join(left, right,
                                       onclause=onclause,
                                       isouter=is_outer)

            # Consume the detail
            if detail_key not in star_tables:
                raise ModelError("Detail table '{}' not in star. Missing join?"
                                 .format(_format_key(detail_key)))

            # The table is consumed by the join product, becomes the join
            # product itself.
            star_tables[detail_key] = star
            star_tables[master_key] = star

        return star


class QueryContext(object):
    """Context for execution of a query with given set of attributes and
    underlying star schema. The context is used for providing columns for
    attributes and generating conditions for cells. Context is reponsible for
    proper compilation of attribute expressions.

    Attributes:

    * `star` – a SQL expression object representing joined star for base
      attributes of the query. See :meth:`StarSchema.get_star` for more
      information

    .. versionadded:: 1.1
    """

    def __init__(self, star_schema, attributes, hierarchies=None,
                 parameters=None, safe_labels=None):
        """Creates a query context for `cube`.

        * `attributes` – list of all attributes that are relevant to the
           query. The attributes must be sorted by their dependency.
        * `hierarchies` is a dictionary of dimension hierarchies. Keys are
           tuples of names (`dimension`, `hierarchy`). The dictionary should
           contain default dimensions as (`dimension`, Null) tuples.
        * `safe_labels` – if `True` then safe column labels are created. Used
           for SQL dialects that don't support characters such as dot ``.`` in
           column labels.  See :meth:`QueryContext.column` for more
           information.

        `attributes` are objects that have attributes: `ref` – attribute
        reference, `is_base` – `True` when attribute does not depend on any
        other attribute and can be directly mapped to a column, `expression` –
        arithmetic expression, `function` – aggregate function (for
        aggregates only).

        Note: in the future the `hierarchies` dictionary might change just to
        a hierarchy name (a string), since hierarchies and dimensions will be
        both top-level objects.

        """

        # Note on why attributes have to be sorted: We don'd have enough
        # information here to get all the dependencies and we don't want this
        # object to depend on the complex Cube model object, just attributes.

        self.star_schema = star_schema

        self.attributes = object_dict(attributes, True)
        self.hierarchies = hierarchies
        self.safe_labels = safe_labels

        # Collect base attributes
        #
        base_names = [attr.ref for attr in attributes if attr.is_base]
        dependants = [attr for attr in attributes if not attr.is_base]

        # This is "the star" to be used by the owners of the context to select
        # from.
        #
        self.star = star_schema.get_star(base_names)
        # TODO: determne from self.star

        # Collect all the columns
        #
        bases = {attr:self.star_schema.column(attr) for attr in base_names}
        bases[FACT_KEY_LABEL] = self.star_schema.fact_key_column

        self._columns = compile_attributes(bases, dependants, parameters,
                                           star_schema.label)

        self.label_attributes = {}
        if self.safe_labels:
            # Re-label the columns using safe labels. It is up to the owner of
            # the context to determine which column is which attribute

            for i, item in enumerate(list(self._columns.items())):
                attr, column = item
                label = "a{}".format(i)
                self._columns[attr] = column.label(label)
                self.label_attributes[label] = attr
        else:
            for attr in attributes:
                attr = attr.ref
                column = self._columns[attr]
                self._columns[attr] = column.label(attr)
                # Identity mappign
                self.label_attributes[attr] = attr

    def column(self, ref):
        """Get a column expression for attribute with reference `ref`. Column
        has the same label as the attribute reference, unless `safe_labels` is
        provided to the query context. If `safe_labels` translation is
        provided, then the column has label according to the translation
        dictionary."""

        try:
            return self._columns[ref]
        except KeyError as e:
            # This should not happen under normal circumstances. If this
            # exception is raised, it very likely means that the owner of the
            # query contexts forgot to do something.
            raise InternalError("Missing column '{}'. Query context not "
                                "properly initialized or dependencies were "
                                "not correctly ordered?".format(ref))

    def get_labels(self, columns):
        """Returns real attribute labels for columns `columns`. It is highly
        recommended that the owner of the context uses this method before
        iterating over statement result."""

        if self.safe_labels:
            return [self.label_attributes.get(column.name, column.name)
                    for column in columns]
        else:
            return [col.name for col in columns]

    def get_columns(self, refs):
        """Get columns for attribute references `refs`.  """

        return [self._columns[ref] for ref in refs]

    def condition_for_cell(self, cell):
        """Returns a condition for cell `cell`. If cell is empty or cell is
        `None` then returns `None`."""

        if not cell:
            return None

        condition = and_(*self.conditions_for_cuts(cell.cuts))

        return condition

    def conditions_for_cuts(self, cuts):
        """Constructs conditions for all cuts in the `cell`. Returns a list of
        SQL conditional expressions.
        """

        conditions = []

        for cut in cuts:
            hierarchy = str(cut.hierarchy) if cut.hierarchy else None

            if isinstance(cut, PointCut):
                path = cut.path
                condition = self.condition_for_point(str(cut.dimension),
                                                     path,
                                                     hierarchy, cut.invert)

            elif isinstance(cut, SetCut):
                set_conds = []

                for path in cut.paths:
                    condition = self.condition_for_point(str(cut.dimension),
                                                         path,
                                                         str(cut.hierarchy),
                                                         invert=False)
                    set_conds.append(condition)

                condition = sql.expression.or_(*set_conds)

                if cut.invert:
                    condition = sql.expression.not_(condition)

            elif isinstance(cut, RangeCut):
                condition = self.range_condition(str(cut.dimension),
                                                 hierarchy,
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

        levels = self.level_keys(dim, hierarchy, path)

        for level_key, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level_key)
            conditions.append(column == value)

        condition = sql.expression.and_(*conditions)

        if invert:
            condition = sql.expression.not_(condition)

        return condition

    def range_condition(self, dim, hierarchy, from_path, to_path,
                        invert=False):
        """Return a condition for a hierarchical range (`from_path`,
        `to_path`). Return value is a `Condition` tuple."""

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
        # TODO: make this non-recursive

        if not path:
            return None

        last = self._boundary_condition(dim, hierarchy, path[:-1], bound,
                                        first=False)

        levels = self.level_keys(dim, hierarchy, path)

        conditions = []

        for level_key, value in zip(levels[:-1], path[:-1]):
            column = self.column(level_key)
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

        column = self.column(levels[-1])
        conditions.append(operator(column, path[-1]))
        condition = sql.expression.and_(*conditions)

        if last is not None:
            condition = sql.expression.or_(condition, last)

        return condition

    def level_keys(self, dimension, hierarchy, path):
        """Return list of key attributes of levels for `path` in `hierarchy`
        of `dimension`."""

        # Note: If something does not work here, make sure that hierarchies
        # contains "default hierarchy", that is (dimension, None) tuple.
        #
        try:
            levels = self.hierarchies[(str(dimension), hierarchy)]
        except KeyError as e:
            raise InternalError("Unknown hierarchy '{}'. Hierarchies are "
                                "not properly initialized (maybe missing "
                                "default?)".format(e))

        depth = 0 if not path else len(path)

        if depth > len(levels):
            levels_str = ", ".join(levels)
            raise HierarchyError("Path '{}' is longer than hierarchy. "
                                 "Levels: {}".format(path, levels))

        return levels[0:depth]

    def column_for_split(self, split_cell, label=None):
        """Create a column for a cell split from list of `cust`."""

        condition = self.condition_for_cell(split_cell)
        split_column = sql.expression.case([(condition, True)],
                                           else_=False)

        label = label or SPLIT_DIMENSION_NAME

        return split_column.label(label)

