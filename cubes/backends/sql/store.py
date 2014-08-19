# -*- encoding=utf -*-

from __future__ import absolute_import

from .browser import SnowflakeBrowser
from .mapper import SnowflakeMapper
from ...logging import get_logger
from ...common import coalesce_options
from ...stores import Store
from ...errors import *
from ...browser import *
from ...computation import *
from .query import QueryBuilder
from .utils import CreateTableAsSelect, InsertIntoAsSelect, CreateOrReplaceView

try:
    import sqlalchemy
    import sqlalchemy.sql as sql
    from sqlalchemy.engine import reflection
except ImportError:
    from ...common import MissingPackage
    reflection = sqlalchemy = sql = MissingPackage("sqlalchemy",
                                                   "SQL aggregation browser")


__all__ = [
    "create_sqlalchemy_engine",
    "SQLStore"
]


# Data types of options passed to sqlalchemy.create_engine
# This is used to coalesce configuration string values into appropriate types
SQLALCHEMY_OPTION_TYPES = {
        "case_sensitive": "bool",
        "case_insensitive": "bool",
        "convert_unicode": "bool",
        "echo": "bool",
        "echo_pool": "bool",
        "implicit_returning": "bool",
        "label_length": "int",
        "max_overflow": "int",
        "pool_size": "int",
        "pool_recycle": "int",
        "pool_timeout": "int",
        "supports_unicode_binds": "bool"
}

# Data types of options passed to the workspace, browser and mapper
# This is used to coalesce configuration string values
OPTION_TYPES = {
        "include_summary": "bool",
        "include_cell_count": "bool",
        "use_denormalization": "bool",
        "safe_labels": "bool"
}


####
# Backend related functions
###
def ddl_for_model(url, model, fact_prefix=None,
                  fact_suffix=None, dimension_prefix=None,
                  dimension_suffix=None, schema_type=None):
    """Create a star schema DDL for a model.

    Parameters:

    * `url` - database url – no connection will be created, just used by
       SQLAlchemy to determine appropriate engine backend
    * `cube` - cube to be described
    * `dimension_prefix` - prefix used for dimension tables
    * `dimension_suffix` - suffix used for dimension tables
    * `schema_type` - ``logical``, ``physical``, ``denormalized``

    As model has no data storage type information, following simple rule is
    used:

    * fact ID is an integer
    * all keys are strings
    * all attributes are strings
    * all measures are floats

    .. warning::

        Does not respect localized models yet.

    """
    raise NotImplementedError


def create_sqlalchemy_engine(url, options, prefix="sqlalchemy_"):
    """Create a SQLAlchemy engine from `options`. Options have prefix
    ``sqlalchemy_``"""
    sa_keys = [key for key in options.keys() if key.startswith(prefix)]
    sa_options = {}
    for key in sa_keys:
        sa_key = key[11:]
        sa_options[sa_key] = options.pop(key)

    sa_options = coalesce_options(sa_options, SQLALCHEMY_OPTION_TYPES)
    engine = sqlalchemy.create_engine(url, **sa_options)

    return engine


class SQLStore(Store):

    def model_provider_name(self):
        return 'default'

    default_browser_name = "snowflake"

    def __init__(self, url=None, engine=None, schema=None, **options):
        """
        The options are:

        Required (one of the two, `engine` takes precedence):

        * `url` - database URL in form of:
          ``backend://user:password@host:port/database``
        * `sqlalchemy_options` - this backend accepts options for SQLAlchemy
          in the form: ``option1=value1[&option2=value2]...``
        * `engine` - SQLAlchemy engine - either this or URL should be provided

        Optional:

        * `schema` - default schema, where all tables are located (if not
          explicitly stated otherwise)
        * `fact_prefix` - used by the snowflake mapper to find fact table for a
          cube, when no explicit fact table name is specified
        * `dimension_prefix` - used by snowflake mapper to find dimension
          tables when no explicit mapping is specified
        * `fact_suffix` - used by the snowflake mapper to find fact table for a
          cube, when no explicit fact table name is specified
        * `dimension_suffix` - used by snowflake mapper to find dimension
          tables when no explicit mapping is specified
        * `dimension_schema` – schema where dimension tables are stored, if
          different than common schema.

        Options for denormalized views:

        * `use_denormalization` - browser will use dernormalized view instead
          of snowflake
        * `denormalized_view_prefix` - if denormalization is used, then this
          prefix is added for cube name to find corresponding cube view
        * `denormalized_view_schema` - schema wehere denormalized views are
          located (use this if the views are in different schema than fact
          tables, otherwise default schema is going to be used)
        """
        if not engine and not url:
            raise ArgumentError("No URL or engine specified in options, "
                                "provide at least one")
        if engine and url:
            raise ArgumentError("Both engine and URL specified. Use only one.")

        # Create a copy of options, because we will be popping from it
        options = dict(options)

        if not engine:
            # Process SQLAlchemy options
            engine = create_sqlalchemy_engine(url, options)

        # TODO: get logger from workspace that opens this store
        self.logger = get_logger()

        self.connectable = engine
        self.schema = schema

        # Load metadata here. This might be too expensive operation to be
        # performed on every request, therefore it is recommended to have one
        # shared open store per process. SQLAlchemy will take care about
        # necessary connections.

        self.metadata = sqlalchemy.MetaData(bind=self.connectable,
                                            schema=self.schema)

        self.options = coalesce_options(options, OPTION_TYPES)

    def _drop_table(self, table, schema, force=False):
        """Drops `table` in `schema`. If table exists, exception is raised
        unless `force` is ``True``"""

        view_name = str(table)
        preparer = self.connectable.dialect.preparer(self.connectable.dialect)
        full_name = preparer.format_table(table)

        if table.exists() and not force:
            raise WorkspaceError("View or table %s (schema: %s) already exists." % \
                               (view_name, schema))

        inspector = sqlalchemy.engine.reflection.Inspector.from_engine(self.connectable)
        view_names = inspector.get_view_names(schema=schema)

        if view_name in view_names:
            # Table reflects a view
            drop_statement = "DROP VIEW %s" % full_name
            self.connectable.execute(drop_statement)
        else:
            # Table reflects a table
            table.drop(checkfirst=False)

    # TODO: broken
    def create_denormalized_view(self, cube, view_name=None, materialize=False,
                                 replace=False, create_index=False,
                                 keys_only=False, schema=None):
        """Creates a denormalized view named `view_name` of a `cube`. If
        `view_name` is ``None`` then view name is constructed by pre-pending
        value of `denormalized_view_prefix` from workspace options to the cube
        name. If no prefix is specified in the options, then view name will be
        equal to the cube name.

        Options:

        * `materialize` - whether the view is materialized (a table) or
          regular view
        * `replace` - if `True` then existing table/view will be replaced,
          otherwise an exception is raised when trying to create view/table
          with already existing name
        * `create_index` - if `True` then index is created for each key
          attribute. Can be used only on materialized view, otherwise raises
          an exception
        * `keys_only` - if ``True`` then only key attributes are used in the
          view, all other detail attributes are ignored
        * `schema` - target schema of the denormalized view, if not specified,
          then `denormalized_view_schema` from options is used if specified,
          otherwise default workspace schema is used (same schema as fact
          table schema).
        """

        # TODO: this method requires more attention, it is just appropriated
        # for recent cubes achanges

        engine = self.connectable

        # TODO: we actually don't need browser, we are just reusing its
        # __init__ for other objects. This should be recreated here.
        browser = SnowflakeBrowser(cube, self, schema=schema)
        builder = QueryBuilder(browser)

        key_attributes = []
        for dim in cube.dimensions:
            key_attributes += dim.key_attributes()

        if keys_only:
            statement = builder.denormalized_statement(attributes=key_attributes, expand_locales=True)
        else:
            statement = builder.denormalized_statement(expand_locales=True)

        schema = schema or self.options.get("denormalized_view_schema") or self.schema

        dview_prefix = self.options.get("denormalized_view_prefix","")
        view_name = view_name or dview_prefix + cube.name

        if browser.mapper.fact_name == view_name and schema == browser.mapper.schema:
            raise WorkspaceError("target denormalized view is the same as source fact table")

        table = sqlalchemy.Table(view_name, self.metadata,
                                 autoload=False, schema=schema)

        if table.exists():
            self._drop_table(table, schema, force=replace)

        if materialize:
            # TODO: Handle this differently for postgres
            create_view = CreateTableAsSelect(table, statement)
        else:
            create_view = CreateOrReplaceView(table, statement)

        self.logger.info("creating denormalized view %s (materialized: %s)" \
                                            % (str(table), materialize))
        # print("SQL statement:\n%s" % statement)
        engine.execute(create_view)

        if create_index:
            if not materialize:
                raise WorkspaceError("Index can be created only on a materialized view")

            # self.metadata.reflect(schema = schema, only = [view_name] )
            table = sqlalchemy.Table(view_name, self.metadata,
                                     autoload=True, schema=schema)

            insp = reflection.Inspector.from_engine(engine)
            insp.reflecttable(table, None)

            for attribute in key_attributes:
                label = attribute.ref()
                self.logger.info("creating index for %s" % label)
                column = table.c[label]
                name = "idx_%s_%s" % (view_name, label)
                index = sqlalchemy.schema.Index(name, column)
                index.create(engine)

        return statement

    def validate_model(self):
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

        for cube in self.model.cubes:
            browser = self.browser(cube)
            issues += browser.validate()

        return issues

    ########################################################################
    ########################################################################
    ##
    ## Aggregates
    ##
    """
    Aggregate specification:
        * cube
        * dimensions, "grain" (levels) + required dimensions
        * aggregate schema
        * aggregate table
        * create_dimensions? flag

    Grain dimension:
        * Name: prefix_dimension_level
        * Attributes: all level attributes
        * NON-UNIQUE level key: join will have to be composed of multiple keys
        * UNIQUE level key: join might be based on level key
    """

    def _create_indexes(self, table, columns, schema=None):
        """Create indexes on `table` in `schema` for `columns`"""

        raise NotImplementedError

    def create_conformed_rollup(self, cube, dimension, level=None, hierarchy=None,
                                schema=None, dimension_prefix=None, dimension_suffix=None,
                                replace=False):
        """Extracts dimension values at certain level into a separate table.
        The new table name will be composed of `dimension_prefix`, dimension
        name and suffixed by dimension level. For example a product dimension
        at category level with prefix `dim_` will be called
        ``dim_product_category``

        Attributes:

        * `dimension` – dimension to be extracted
        * `level` – grain level
        * `hierarchy` – hierarchy to be used
        * `schema` – target schema
        * `dimension_prefix` – prefix used for the dimension table
        * `dimension_suffix` – suffix used for the dimension table
        * `replace` – if ``True`` then existing table will be replaced,
          otherwise an exception is raised if table already exists.
        """
        mapper = SnowflakeMapper(cube, cube.mappings, schema=schema, **self.options)
        context = QueryContext(cube, mapper, schema=schema, etadata=self.metadata)

        dimension = cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)
        if level:
            depth = hierarchy.level_index(dimension.level(level))+1
        else:
            depth = len(hierarchy)

        if depth == 0:
            raise ArgumentError("Depth for dimension values should not be 0")
        elif depth is not None:
            levels = hierarchy.levels[0:depth]


        attributes = []
        for level in levels:
            attributes.extend(level.attributes)

        statement = context.denormalized_statement(attributes=attributes,
                                                    include_fact_key=False)

        group_by = [context.column(attr) for attr in attributes]
        statement = statement.group_by(*group_by)

        table_name = "%s%s%s_%s" % (dimension_prefix or "", dimension_suffix or "",
                                    str(dimension), str(level))
        self.create_table_from_statement(table_name, statement, schema,
                                            replace, insert=True)

    def create_conformed_rollups(self, cube, dimensions, grain=None, schema=None,
                                 dimension_prefix=None, dimension_suffix=None,
                                 replace=False):
        """Extract multiple dimensions from a snowflake. See
        `extract_dimension()` for more information. `grain` is a dictionary
        where keys are dimension names and values are levels, if level is
        ``None`` then all levels are considered."""

        grain = grain or {}

        for dim in dimensions:
            dim = cube.dimension(dim)
            level = grain.get(str(dim))
            hierarchy = dim.hierarchy()
            if level:
                level_index = hierarchy.level_index(level)
            else:
                level_index = len(hierarchy)

            for depth in range(0,level_index):
                level = hierarchy[depth]
                self.create_conformed_rollup(cube, dim, level=level,
                                    schema=schema,
                                    dimension_prefix=dimension_prefix or "",
                                    dimension_suffix=dimension_suffix or "",
                                    replace=replace)

    def create_table_from_statement(self, table_name, statement, schema,
                                     replace=False, insert=False):
        """Creates or replaces a table from statement.

        Arguments:

        * `table_name` - name of target table
        * `schema` – target table schema
        * `statement` – SQL statement used to get structure of the new table
        * `insert` – if `True` then data are inserted from the statement,
          otherwise only empty table is created. Defaut is `False`
        * `replace` – if `True` old table will be dropped, otherwise if table
          already exists an exception is raised.
        """

        #
        # Create table
        #
        table = sqlalchemy.Table(table_name, self.metadata,
                                 autoload=False, schema=schema)

        if table.exists():
            self._drop_table(table, schema, force=replace)

        for col in statement.columns:
            # mysql backend requires default string length
            if self.connectable.name == "mysql" \
                    and isinstance(col.type, sqlalchemy.String) \
                    and not col.type.length:
                col_type = sqlalchemy.String(255)
            else:
                col_type = col.type

            new_col = sqlalchemy.Column(col.name, col_type)
            table.append_column(new_col)

        self.logger.info("creating table '%s'" % str(table))
        self.metadata.create_all(tables=[table])

        if insert:
            self.logger.debug("inserting into table '%s'" % str(table))
            insert_statement = InsertIntoAsSelect(table, statement,
                                                  columns=statement.columns)
            self.connectable.execute(insert_statement)

        return table

    def create_cube_aggregate(self, browser, table_name=None, dimensions=None,
                              dimension_links=None, schema=None,
                              replace=False):
        """Creates an aggregate table. If dimensions is `None` then all cube's
        dimensions are considered.

        Arguments:

        * `dimensions`: list of dimensions to use in the aggregated cuboid, if
          `None` then all cube dimensions are used
        * `dimension_links`: list of dimensions that are required for each
          aggregation (for example a date dimension in most of the cases). The
          list should be a subset of `dimensions`.
        * `aggregates_prefix`: aggregated table prefix
        * `aggregates_schema`: schema where aggregates are stored

        """

        if browser.store != self:
            raise ArgumentError("Can create aggregate table only within "
                                "the same store")

        schema = schema or self.options.get("aggregates_schema", self.schema)
        prefix = self.options.get("aggregates_prefix","")
        table_name = table_name or prefix + cube.name

        # Just a shortcut
        cube = browser.cube
        if dimensions:
            dimensions = [cube.dimension(dim) for dim in dimensions]
        else:
            dimensions = cube.dimensions

        # Collect keys that are going to be used for aggregations
        keys = []
        for dimension in dimensions:
            keys += [level.key for level in dimension.hierarchy().levels]

        builder = QueryBuilder(browser)

        if builder.snowflake.fact_name == table_name \
                and builder.snowflake.schema == schema:
            raise ArgumentError("target is the same as source fact table")

        drilldown = {}

        for dim in dimensions:
            level = dim.hierarchy().levels[-1]
            drilldown[str(dim)] = level

        cell = Cell(cube)
        drilldown = Drilldown(drilldown, cell)

        # Create dummy statement of all dimension level keys for
        # getting structure for table creation
        # TODO: attributes/keys?
        statement = builder.aggregation_statement(cell,
                                                  drilldown,
                                                  cube.aggregates)

        #
        # Create table
        #
        table = self.create_table_from_statement(table_name,
                                                  statement,
                                                  schema=schema,
                                                  replace=replace,
                                                  insert=False)

        cuboids = hierarchical_cuboids(dimensions,
                                        required=dimension_links)

        for cuboid in cuboids:

            # 'cuboid' is described as a list of ('dimension', 'level') tuples
            # where 'level' is deepest level to be considered

            self.logger.info("aggregating cuboid %s" % (cuboid, ) )

            dd = {}
            keys = None
            for dim, level in cuboid:
                dd[str(dim)] = level
                dim = cube.dimension(dim)
                hier = dim.hierarchy()
                levels = hier.levels_for_depth(hier.level_index(level)+1)
                keys = [l.key for l in levels]

            dd = Drilldown(dd, cell)

            statement = builder.aggregation_statement(cell,
                                                      aggregates=cube.aggregates,
                                                      attributes=keys,
                                                      drilldown=drilldown)
            self.logger.info("inserting")
            insert = InsertIntoAsSelect(table, statement,
                                        columns=statement.columns)
            self.connectable.execute(str(insert))
