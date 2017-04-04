# -*- encoding=utf -*-
"""
cubes.sql.query
~~~~~~~~~~~~~~~

Star/snowflake schema query construction structures

"""

from typing import (
        Any,
        cast,
        Callable,
        Collection,
        Dict,
        List,
        Mapping,
        NamedTuple,
        Optional,
        Set,
        Tuple,
        Union,
    )

from ..types import JSONType

from . import sqlalchemy as sa

from logging import Logger, getLogger
from collections import namedtuple

from ..metadata import object_dict
from ..metadata.dimension import HierarchyPath
from ..metadata.physical import ColumnReference, JoinKey, Join, JoinMethod
from ..metadata.attributes import AttributeBase
from ..errors import InternalError, ModelError, ArgumentError, HierarchyError
from ..query.constants import SPLIT_DIMENSION_NAME
from ..query.cells import Cell, Cut, PointCut, SetCut, RangeCut

from .expressions import compile_attributes


# Default label for all fact keys
FACT_KEY_LABEL = '__fact_key__'
DEFAULT_FACT_KEY = 'id'

# Attribute -> Column
# IF attribute has no 'expression' then mapping is used
# IF attribute has expression, the expression is used and underlying mappings

# 
# END OF FREE TYPES
# --------------------------------------------------------------------------

# TODO: [typing] Make this public
class _TableKey(NamedTuple):
    schema: Optional[str]
    table: str

# FIXME: [typing] Move this to _TableKey in Python 3.6.1 as __str__
def _format_key(key: _TableKey) -> str:
    """Format table key `key` to a string."""
    table = key.table or "<FACT>"

    if key.schema is not None:
        return f"{key.schema}.{table}"
    else:
        return table

# Internal table reference
class _TableRef(NamedTuple):
    # Database schema
    schema: Optional[str]
    # Table name
    name: str
    # Optional table alias instead of name
    alias: Optional[str]
    # Table key (for caching or referencing)
    key: _TableKey
    # SQLAlchemy Table object, reflected
    table: sa.FromClause
    # join which joins this table as a detail
    join: Optional[Join]

class SchemaError(InternalError):
    """Error related to the physical star schema."""
    pass


class NoSuchTableError(SchemaError):
    """Error related to the physical star schema."""
    pass


class NoSuchAttributeError(SchemaError):
    """Error related to the physical star schema."""
    pass


class StarSchema:
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

    label: str
    metadata: sa.MetaData
    # FIXME: [typing] rename to `mapping` (sg.) or `column_references`
    mappings: Mapping[str, ColumnReference]
    # joins: Collection[_JoinWildType]
    joins: Collection[Join]
    schema: Optional[str]
    table_expressions: Mapping[str, sa.FromClause]

    # FIXME: [typing] this should be ColumnExpression or some superclass of Col
    _columns: Dict[str, sa.ColumnElement]
    _tables: Dict[_TableKey, _TableRef]
    
    logger: Logger
    fact_name: str
    fact_table: sa.FromClause
    fact_key: str
    # FIXME: [typing] change to SA expression (same as above)
    fact_key_column: sa.Column

    def __init__(self,
            label: str,
            metadata: sa.MetaData,
            # FIXME: [typing] This should be already prepared
            mappings: Mapping[str, ColumnReference],
            fact_name: str,
            fact_key: Optional[str]=None,
            joins: Optional[Collection[Join]]=None,
            tables: Optional[Mapping[str, sa.FromClause]]=None,
            schema: Optional[str]=None) -> None:

        # TODO: expectation is, that the snowlfake is already localized, the
        # owner of the snowflake should generate one snowflake per locale.

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

        self.logger = getLogger("cubes.starschema")

        # TODO: perform JOIN discovery based on foreign keys

        # Fact Table
        # ----------

        # Fact Initialization
        self.fact_name = fact_name
        self.fact_table = self.physical_table(fact_name)

        # Try to get the fact key
        if fact_key is not None:
            try:
                self.fact_key_column = self.fact_table.columns[self.fact_key]
            except KeyError:
                raise ModelError(f"Unknown column '{fact_key}' "
                                 f"in fact table '{fact_name}' for '{label}'.")
        elif DEFAULT_FACT_KEY in self.fact_table.columns:
            self.fact_key_column = self.fact_table.columns[DEFAULT_FACT_KEY]
        else:
            # Get the first column
            self.fact_key_column = list(self.fact_table.columns)[0]

        self.fact_key_column = self.fact_key_column.label(FACT_KEY_LABEL)

        # Rest of the initialization
        # --------------------------
        self._collect_tables()

    def _collect_tables(self) -> None:
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
        fact_table = _TableRef(
                schema=self.schema,
                name=self.fact_name,
                alias=self.fact_name,
                key=_TableKey(self.schema, self.fact_name),
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
        seen: Set[_TableKey] = set()

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

            key = _TableKey(join.detail.schema or self.schema, alias)

            if key in seen:
                raise ModelError("Detail table '{}' joined twice in star"
                                 " schema {}. Join alias is required."
                                 .format(_format_key(key), self.label))
            seen.add(key)

            self._tables[key] = _TableRef(
                                    table=table,
                                    schema=join.detail.schema,
                                    name=join.detail.table,
                                    alias=alias,
                                    key=key,
                                    join=join,
                                )


    def table(self, key: _TableKey, role: str=None) -> _TableRef:
        """Return a table reference for `key`. `schema` should be ``None`` for
        named table expressions, which take precedence before the physical
        tables in the default schema. If there is no named table expression
        then physical table is considered.

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

        assert(key is not None, "Table key should not be None")

        key = _TableKey(key[0] or self.schema, key[1] or self.fact_name)

        try:
            return self._tables[key]
        except KeyError:
            if role is not None:
                role_str = " (as {})".format(role)
            else:
                role_str = ""

            schema_str = f'"{key[0]}".' if key[0] is not None else ""

            raise SchemaError(f"Unknown star table {schema_str}"
                              f"\"{key[1]}\"{role_str}. Missing join?")

    def physical_table(self, name: str, schema: Optional[str]=None) \
            -> sa.FromClause:
        """Return a physical table or table expression by name, regardless
        whether it exists or not in the star."""

        # Return a statement or an explicitly craeted table if it exists
        if schema is None and name in self.table_expressions:
            return self.table_expressions[name]

        coalesced_schema: Optional[str]
        coalesced_schema = schema or self.schema

        table: sa.Table

        try:
            table = sa.Table(name,
                             self.metadata,
                             autoload=True,
                             schema=coalesced_schema)

        except sa.NoSuchTableError:
            schema_str: str
            if schema is not None:
                schema_str = f" in schema '{schema}'"
            else:
                schema_str = ""

            raise NoSuchTableError(f"No such fact table '{name}'{schema_str}")

        return table

    def column(self, logical: str) -> sa.ColumnElement:
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

        column_ref: ColumnReference

        if logical in self._columns:
            return self._columns[logical]

        try:
            column_ref = self.mappings[logical]
        except KeyError:
            if logical == FACT_KEY_LABEL:
                return self.fact_key_column
            else:
                raise NoSuchAttributeError(logical)

        table_key = _TableKey(column_ref.schema or self.schema,
                              column_ref.table or self.fact_name)

        table = self.table(table_key).table

        try:
            column = table.columns[column_ref.column]
        except KeyError:
            avail: str
            avail = ", ".join(str(c) for c in table.columns)
            raise SchemaError(f"Unknown column '{column_ref.column}' "
                              f"in table '{column_ref.table}' "
                              f"possible: {avail}")

        # Apply the `extract` operator/function on date field
        #
        if column_ref.extract is not None:
            column = sa.extract(column_ref.extract, column)

        if column_ref.function is not None:
            # TODO: add some protection here for the function name!
            column = getattr(sa.func, column_ref.function)(column)

        column = column.label(logical)

        # Cache the column
        self._columns[logical] = column

        return column

    def _master_key(self, join: Join) -> _TableKey:
        """Generate join master key, use schema defaults"""
        return _TableKey(join.master.schema or self.schema,
                         join.master.table or self.fact_name)

    def _detail_key(self, join: Join) -> _TableKey:
        """Generate join detail key, use schema defaults"""
        # Note: we don't include fact as detail table by default. Fact can not
        # be detail (at least for now, we don't have a case where it could be)
        detail_table: str
        if join.detail.table is None:
            raise ModelError("Missing join detail table in '{join}'")
        else:
            detail_table = join.alias or join.detail.table

        return _TableKey(join.detail.schema or self.schema, detail_table)

    def required_tables(self, attributes: Collection[str]) -> List[_TableRef]:
        """Get all tables that are required to be joined to get `attributes`.
        `attributes` is a list of `StarSchema` attributes (or objects with
        same kind of attributes).
        """

        # Attribute: (schema, table, column)
        # Join: ((schema, table, column), (schema, table, column), alias)

        if not self.joins:
            self.logger.debug("no joins to be searched for")

        # Get the physical mappings for attributes
        column_refs: Collection[ColumnReference]
        column_refs = [self.mappings[attr] for attr in attributes]

        # Generate table keys
        # FIXME: [typing] We need to resolve this non-optional
        # ColumnReference.table. See also: column() method of this class.
        relevant: Set[_TableRef]
        relevant = set(self.table(_TableKey(ref.schema, ref.table))
                       for ref in column_refs)

        # Dependencies
        # ------------
        # `required` now contains tables that contain requested `attributes`.
        # Nowe we have to resolve all dependencies.

        required: Dict[_TableKey, _TableRef] = {}

        while relevant:
            table = relevant.pop()
            required[table.key] = table

            if not table.join:
                continue

            # Add Master if not already added
            key: _TableKey
            key = self._master_key(table.join)
            if key not in required:
                relevant.add(self.table(key))

            # Add Detail if not already added
            key = self._detail_key(table.join)
            if key not in required:
                relevant.add(self.table(key))

        # Sort the tables
        # ---------------

        fact_key: _TableKey
        fact_key = _TableKey(self.schema, self.fact_name)

        fact: _TableRef
        fact = self.table(fact_key, "fact master")

        masters: Dict[_TableKey, _TableRef]
        masters = {}
        masters[fact_key] = fact

        sorted_tables: List[_TableRef]
        sorted_tables = [fact]

        while required:
            details = [table for table in required.values()
                       if table.join is not None
                       and self._master_key(table.join) in masters]

            if not details:
                break

            for detail in details:
                masters[detail.key] = detail
                sorted_tables.append(detail)

                del required[detail.key]

        # We should end up with only one table in the list, all of them should
        # be consumed by joins.
        if len(required) > 1:
            keys = [_format_key(table.key)
                    for table in required.values()
                    if table.key != fact_key]

            joined_str = ", ".join(keys)
            raise ModelError(f"Some tables are not joined: {joined_str}")

        return sorted_tables

    # Note: This is "The Method"
    # ==========================

    def get_star(self, attributes: Collection[str]) -> sa.FromClause:
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

        # Collect all the tables first:
        tables: List[_TableRef]
        tables = self.required_tables(attributes)

        # Dictionary of raw tables and their joined products
        # At the end this should contain only one item representing the whole
        # star.
        star_tables: Dict[_TableKey, sa.FromClause]
        star_tables = {table_ref.key: table_ref.table for table_ref in tables}

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
        star: sa.FromClause
        star = tables[0].table

        for table in tables[1:]:
            join: Join

            if table.join is None:
                raise ModelError("Missing join for table '{}'"
                                 .format(_format_key(table.key)))
            else:
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
                master_columns = [master_table.columns[name]
                                  for name in master.columns]
            except KeyError as e:
                raise ModelError('Unable to find master key column "{key}" '
                                 'in table "{table}" for star {schema} '
                                 .format(schema=self.label,
                                         key=e,
                                         table=_format_key(master_key)))

            # Detail table.column
            # -------------------
            try:
                detail_columns = [detail_table.columns[name]
                                  for name in join.detail.columns]
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
            key_conditions: List[sa.ColumnElement]
            key_conditions = [left == right
                              for left, right
                              in zip(master_columns, detail_columns)]
            onclause: sa.ColumnElement
            onclause = sa.and_(*key_conditions)

            # Determine the join type based on the join method. If the method
            # is "detail" then we need to swap the order of the tables
            # (products), because SQLAlchemy provides inteface only for
            # left-outer join.
            left, right = (star, detail_table)

            if join.method is None or join.method == JoinMethod.match:
                is_outer = False
            elif join.method == JoinMethod.master:
                is_outer = True
            elif join.method == JoinMethod.detail:
                # Swap the master and detail tables to perform RIGHT OUTER JOIN
                left, right = (right, left)
                is_outer = True
            else:
                raise ModelError("Unknown join method '%s'" % join.method)

            star = sa.join(left, right, onclause=onclause, isouter=is_outer)

            # Consume the detail
            if detail_key not in star_tables:
                raise ModelError("Detail table '{}' not in star. Missing join?"
                                 .format(_format_key(detail_key)))

            # The table is consumed by the join product, becomes the join
            # product itself.
            star_tables[detail_key] = star
            star_tables[master_key] = star

        return star


# TODO: [typing] Make the hierarchy non-optional, explicit
_WildHierarchyKeyType = Tuple[str, Optional[str]]
_WildHierarchyDictType = Dict[_WildHierarchyKeyType, List[str]]

class QueryContext:
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

    star_schema: StarSchema
    attributes: Dict[str, AttributeBase]
    hierarchies: _WildHierarchyDictType
    safe_labels: bool
    star: sa.FromClause
    _columns: Dict[str, sa.ColumnElement]
    # FIXME: Rename to label_to_attribute or label_attr_map
    label_attributes: Dict[str, str]
    
    # TODO: Pass parameters here
    def __init__(self,
            star_schema: StarSchema,
            attributes: Collection[AttributeBase] ,
            hierarchies: Optional[_WildHierarchyDictType]=None,
            safe_labels: Optional[bool]=False) -> None:
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

        self.attributes = object_dict(attributes, by_ref=True)
        self.hierarchies = hierarchies or {}
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
        bases = {attr: self.star_schema.column(attr) for attr in base_names}
        bases[FACT_KEY_LABEL] = self.star_schema.fact_key_column

        # FIXME: [typing] correct the type once sql.expressions are annotated
        self._columns = compile_attributes(bases=bases,
                                           dependants=dependants,
                                           parameters=None,
                                           label=star_schema.label)  # type: ignore

        self.label_attributes = {}
        if self.safe_labels:
            # Re-label the columns using safe labels. It is up to the owner of
            # the context to determine which column is which attribute

            for i, item in enumerate(self._columns.items()):
                attr_name, column = item
                label = f"a{i}"
                self._columns[attr_name] = column.label(label)
                self.label_attributes[label] = attr_name
        else:
            for attr in attributes:
                column = self._columns[attr.ref]
                self._columns[attr.ref] = column.label(attr.ref)
                # Identity mappign
                self.label_attributes[attr.ref] = attr.ref

    def column(self, ref: str) -> sa.ColumnElement:
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

    def get_labels(self, columns: Collection[sa.ColumnElement]) -> List[str]:
        """Returns real attribute labels for columns `columns`. It is highly
        recommended that the owner of the context uses this method before
        iterating over statement result."""

        if self.safe_labels:
            return [self.label_attributes.get(column.name, column.name)
                    for column in columns]
        else:
            return [col.name for col in columns]

    def get_columns(self, refs: Collection[str]) -> List[sa.ColumnElement]:
        """Get columns for attribute references `refs`.  """

        return [self._columns[ref] for ref in refs]

    def condition_for_cell(self, cell: Cell) -> sa.ColumnElement:
        """Returns a condition for cell `cell`. If cell is empty or cell is
        `None` then returns `None`."""

        condition = sa.and_(*self.conditions_for_cuts(cell.cuts))

        return condition

    def conditions_for_cuts(self, cuts: List[Cut]) -> List[sa.ColumnElement]:
        """Constructs conditions for all cuts in the `cell`. Returns a list of
        SQL conditional expressions.
        """

        conditions: List[sa.ColumnElement]
        conditions = []
        path: HierarchyPath

        for cut in cuts:
            if isinstance(cut, PointCut):
                path = cut.path
                condition = self.condition_for_point(cut.dimension,
                                                     path,
                                                     cut.hierarchy,
                                                     cut.invert)

            elif isinstance(cut, SetCut):
                set_conds: List[sa.ColumnElement] = []

                for path in cut.paths:
                    condition = self.condition_for_point(cut.dimension,
                                                         path,
                                                         cut.hierarchy,
                                                         invert=False)
                    set_conds.append(condition)

                condition = sa.or_(*set_conds)

                if cut.invert:
                    condition = sa.not_(condition)

            elif isinstance(cut, RangeCut):
                condition = self.range_condition(cut.dimension,
                                                 cut.hierarchy,
                                                 cut.from_path,
                                                 cut.to_path, cut.invert)

            else:
                raise ArgumentError("Unknown cut type %s" % type(cut))

            conditions.append(condition)

        return conditions

    def condition_for_point(self,
            dim: str,
            path: HierarchyPath,
            hierarchy: Optional[str]=None,
            invert: bool=False) -> sa.ColumnElement:
        """Returns a `Condition` tuple (`attributes`, `conditions`,
        `group_by`) dimension `dim` point at `path`. It is a compound
        condition - one equality condition for each path element in form:
        ``level[i].key = path[i]``"""

        conditions: List[sa.ColumnElement]
        conditions = []

        levels = self.level_keys(dim, hierarchy, path)

        for level_key, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level_key)
            conditions.append(column == value)

        condition = sa.and_(*conditions)

        if invert:
            condition = sa.not_(condition)

        return condition

    def range_condition(self,
            dim: str,
            hierarchy: Optional[str],
            from_path: Optional[HierarchyPath],
            to_path: Optional[HierarchyPath],
            invert: bool=False) -> sa.ColumnElement:
        """Return a condition for a hierarchical range (`from_path`,
        `to_path`). Return value is a `Condition` tuple."""

        assert(from_path is not None or to_path is not None,
               "Range cut must have at least one boundary")

        conditions: List[sa.ColumnElement]
        conditions = []

        bound_check: Optional[sa.ColumnElement]
        condition: sa.ColumnElement

        # Lower bound check
        #
        bound_check = self._boundary_condition(dim, hierarchy, from_path, 0)
        if bound_check is not None:
            conditions.append(bound_check)

        # Upper bound check
        bound_check = self._boundary_condition(dim, hierarchy, to_path, 1)
        if bound_check is not None:
            conditions.append(bound_check)

        condition = sa.and_(*conditions)

        if invert:
            condition = sa.not_(condition)

        return condition

    def _boundary_condition(self,
            dim: str,
            hierarchy: Optional[str],
            path: Optional[HierarchyPath],
            bound: int,
            first: bool=True) -> Optional[sa.ColumnElement]:
        """Return a `Condition` tuple for a boundary condition. If `bound` is
        1 then path is considered to be upper bound (operators < and <= are
        used), otherwise path is considered as lower bound (operators > and >=
        are used )"""
        # TODO: make this non-recursive

        column: sa.ColumnElement

        if not path:
            return None

        last = self._boundary_condition(dim, hierarchy, path[:-1], bound,
                                        first=False)

        levels = self.level_keys(dim, hierarchy, path)

        conditions: List[sa.ColumnElement] = []

        for level_key, value in zip(levels[:-1], path[:-1]):
            column = self.column(level_key)
            conditions.append(column == value)

        # Select required operator according to bound
        # 0 - lower bound
        # 1 - upper bound
        operator: Callable[[Any, Any], sa.ColumnElement]
        if bound == 1:
            # 1 - upper bound (that is <= and < operator)
            operator = sa.le if first else sa.lt
        else:
            # else - lower bound (that is >= and > operator)
            operator = sa.ge if first else sa.gt

        column = self.column(levels[-1])
        conditions.append(operator(column, path[-1]))
        condition = sa.and_(*conditions)

        if last is not None:
            condition = sa.or_(condition, last)

        return condition

    def level_keys(self,
            dimension: str,
            hierarchy: Optional[str],
            path: HierarchyPath) -> List[str]:
        """Return list of key attributes of levels for `path` in `hierarchy`
        of `dimension`."""

        # Note: If something does not work here, make sure that hierarchies
        # contains "default hierarchy", that is (dimension, None) tuple.
        #
        # FIXME [typing] Make hierarchy non-optional, explicit
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

    def column_for_split(self, split_cell: Cell, label: str=None) \
            -> sa.ColumnElement:
        """Create a column for a cell split from list of `cust`."""

        condition: sa.ColumnElement
        condition = self.condition_for_cell(split_cell)
        split_column = sa.case([(condition, True)],
                                           else_=False)

        label = label or SPLIT_DIMENSION_NAME

        return split_column.label(label)
