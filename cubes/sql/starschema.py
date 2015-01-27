
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


from collections import namedtuple

# Attribute -> Column
# IF attribute has no 'expression' then mapping is used
# IF attribute has expression, the expression is used and underlying mappings

# TODO: do we need epxression here? We want expression to be on top of
# physically mapped objects
Mapping = namedtuple("StarAttribute",
                     ["schema", "table", "column",
                      # Use only one
                      "extract", "unary"])

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

# Internal table reference
_TableRef = namedtuple("TableRef",
                       ["schema", # Database schema
                        "name",   # Table name
                        "alias",  # Optional table alias instead of name
                        "table",  # SQLAlchemy Table object, reflected
                        "join"    # join which joins this table as a detail
                       ]
                    )

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
    """

    def __init__(self, name, metadata, mappings, fact, joins, tables=None,
                 schema=None):

        # TODO: expectation is, that the snowlfake is already localized, the
        # owner of the snowflake should generate one snowflake per locale.

        self.name = name
        self.metadata = metadata
        self.mappings = mappings or {}
        self.joins = joins or []
        self.schema = schema
        self.tables = tables or {}

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
        if isinstance(fact, compat.string_t):
            self.fact_table = self._table(fact)
        else:
            # We expect fact to be a statement
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
        table = _TableRef(self.schema, self.fact_name, table=self.fact_table)
        self.tables[table.key] = table

        # Collect all the detail tables
        # We don't need to collect the master tables as they are expected to
        # be referenced as 'details'. The exception is the fact table that is
        # provided explicitly for the snowflake schema.

        for join in self.joins:
            # just ask for the table

            table = self._table(join.detail.table, join.detail.schema)

            if join.alias:
                table = table.alias(join.alias)

            sftable = StarTable(
                                table=sql_table,
                                schema=join.detail.schema,
                                name=join.detail.table,
                                alias=join.alias,
                                key=(join.detail.schema, join.detail.table),
                                join=join
                            )

            self.tables[table.key] = table

    def _table(self, name, schema=None):
        """Get reflected SQLAlchemy Table metadata or a table from explicitly
        provided dictionary of `tables`."""

        # Return a statement or an explicitly craeted table if it exists
        if not schema and name in self.tables:
            return self.tables[name]

        # Get the new alchemy table, reflected
        schema = schema or self.schema
        key = (name, schema)

        if key in self._tables:
            return self._tables[key]

        try:
            table = sqlalchemy.Table(fact_name, self.metadata,
                                     autoload=True, schema=schema)
        except sqlalchemy.exc.NoSuchTableError:
            in_schema = (" in schema '%s'" % schema) if schema else ""
            msg = "No such fact table '%s'%s." % (name, in_schema)
            raise StarSchemaError(msg)

        self._tables[key] = table
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

        mapping = self.mapping[logical]

        if mapping in self._columns:
            return self._columns[mapping]

        key = (schema or self.schema, mapping.table)
        try:
            table = self._tables[key].table
        except KeyError:
            raise ModelError("Table with reference %s not found. "
                             "Missing join in star '%s'?"
                             % (key, self.cube.name) )

        try:
            column = table.columns[mapping.column]
        except KeyError:
            avail = ", ".join(str(c) for c in table.columns)
            raise SnowflakeError("Unknown column '%s' in table '%s' possible: %s"
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
        mappings = [maping[attr] for attr in attributes]
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
            try:
                detail = self._tables[detail_key]
            except KeyError:
                raise StarSchemaError("Unknown detail table '%s'" % master_key)
            # self.logger.debug("joining table %s" % (table, ))

            join = detail.join
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

    def star(self, attributes, core=None, core_key=None):
        """The main method for generating underlying star schema joins.
        Returns a denormalized JOIN expression that includes all relevant
        tables containing `attributes`.

        `core` is a master table to be used, usually a fact table. The
        `core_key` is a table key of the master table as the joins referenc
        to it.

        Example use:

        .. code-block:: python

            star = star_schema.star(attributes)
            statement = sql.expression.statement(selection,
                                                 from_obj=star,
                                                 whereclause=condition)
            result = engine.execute(statement)
        """

        # Dictionary of raw tables and their joined products
        star = {}
        tables = []

        if core is not None:
            joined_products[core_key] = master
            tables.append(self._tables[core_key])

        # TODO: this does not work with non-cube objects, as this method uses
        # 'depends_on()'
        attributes = get_base_attributes(attributes)

        # Collect all the tables first:
        joins = self.relevant_joins(attributes)
        for join in joins:
            # 1. MASTER
            # Add master table to the list. If fact table (or statement) was
            # explicitly specified, use it instead of the original fact table

            key = (join.master.schema, join.master.table)
            if master is not None and key == core_key:
                table = master_fact
            else:
                table = self.table(join.master.table, join.master.schema)
            joined_products[key] = table

            # 2. DETAIL
            # Add (aliased) detail table to the list. 

            alias = join.alias or join.detail.table
            table = self.table(join.detail.schema, alias)
            key = (join.detail.schema, alias)
            star[key] = table
            tables.append(self.tables[key])

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
            detail_key = (detail.schema, join.alias or detail.table)

            # We need plain tables to get columns for prepare the join
            # condition
            # Master table.column
            # -------------------
            if master_key == core_key and core is not None:
                master_table = core
            else:
                master_table = self.table(master.schema, master.table)

            key = (join.master.schema, join.master.table, join.master.column)

            try:
                master_column = master_table.c[master.column]
            except KeyError:
                raise ModelError('Unable to find master key (schema {schema}) '
                                 '"{table}"."{column}" '.format(join.master))

            # Detail table.column
            # -------------------
            alias = join.alias or join.detail
            detail_table = self.table(join.detail.schema, alias)

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

            # Replace the already joined master
            del star[detail_key]
            star[master_key] = product

        if not star:
            # This should not happen
            raise InternalError("Star is emtpy")

        if len(star) > 1:
            raise ModelError("Some tables are let unjoined: %s"
                             % (star.keys(), ))

        # Return the star – the only remaining join object
        result = list(star.values())[0]

        return result

