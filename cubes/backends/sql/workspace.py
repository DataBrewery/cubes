# -*- coding=utf -*-
from .star import SnowflakeBrowser, QueryContext
from cubes.mapper import SnowflakeMapper, DenormalizedMapper
from cubes.common import get_logger
from cubes.errors import *
from cubes.browser import *
from cubes.computation import *
from cubes.workspace import Workspace

from .utils import CreateTableAsSelect, InsertIntoAsSelect

try:
    import sqlalchemy
    import sqlalchemy.sql as sql
except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")

__all__ = [
    "create_workspace"
]


####
# Backend related functions
###
def ddl_for_model(url, model, fact_prefix=None, dimension_prefix=None, schema_type=None):
    """Create a star schema DDL for a model.

    Parameters:

    * `url` - database url – no connection will be created, just used by
       SQLAlchemy to determine appropriate engine backend
    * `cube` - cube to be described
    * `dimension_prefix` - prefix used for dimension tables
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

def create_workspace(model, **options):
    """Create workspace for `model` with configuration in dictionary
    `options`. This method is used by the slicer server.

    The options are:

    Required (one of the two, `engine` takes precedence):

    * `url` - database URL in form of:
      ``backend://user:password@host:port/database``
    * `engine` - SQLAlchemy engine - either this or URL should be provided

    Optional:

    * `schema` - default schema, where all tables are located (if not
      explicitly stated otherwise)
    * `fact_prefix` - used by the snowflake mapper to find fact table for a
      cube, when no explicit fact table name is specified
    * `dimension_prefix` - used by snowflake mapper to find dimension tables
      when no explicit mapping is specified
    * `dimension_schema` – schema where dimension tables are stored, if
      different than common schema.

    Options for denormalized views:

    * `use_denormalization` - browser will use dernormalized view instead of
      snowflake
    * `denormalized_view_prefix` - if denormalization is used, then this
      prefix is added for cube name to find corresponding cube view
    * `denormalized_view_schema` - schema wehere denormalized views are
      located (use this if the views are in different schema than fact tables,
      otherwise default schema is going to be used)
    """
    engine = options.get("engine")

    if engine:
        del options["engine"]
    else:
        try:
            db_url = options["url"]
        except KeyError:
            raise ArgumentError("No URL or engine specified in options, "
                                "provide at least one")
        engine = sqlalchemy.create_engine(db_url)


    workspace = SQLStarWorkspace(model, engine, **options)

    return workspace

class SQLStarWorkspace(Workspace):
    """Factory for browsers"""
    def __init__(self, model, engine, **options):
        """Create a workspace. For description of options see
        `create_workspace()` """

        super(SQLStarWorkspace, self).__init__(model)

        self.logger = get_logger()

        self.engine = engine
        self.schema = options.get("schema")
        self.metadata = sqlalchemy.MetaData(bind=self.engine,schema=self.schema)
        self.options = options

    def browser(self, cube, locale=None):
        """Returns a browser for a `cube`."""
        model = self.localized_model(locale)
        cube = model.cube(cube)
        browser = SnowflakeBrowser(cube, self.engine, locale=locale,
                              metadata=self.metadata,
                              **self.options)
        return browser

    def _drop_table(self, table, schema, force=False):
        """Drops `table` in `schema`. If table exists, exception is raised
        unless `force` is ``True``"""

        view_name = str(table)
        preparer = self.engine.dialect.preparer(self.engine.dialect)
        full_name = preparer.format_table(table)

        if table.exists() and not force:
            raise WorkspaceError("View or table %s (schema: %s) already exists." % \
                               (view_name, schema))

        inspector = sqlalchemy.engine.reflection.Inspector.from_engine(self.engine)
        view_names = inspector.get_view_names(schema=schema)

        if view_name in view_names:
            # Table reflects a view
            drop_statement = "DROP VIEW %s" % full_name
            self.engine.execute(drop_statement)
        else:
            # Table reflects a table
            table.drop(checkfirst=False)

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

        cube = self.model.cube(cube)

        mapper = SnowflakeMapper(cube, cube.mappings, **self.options)
        context = QueryContext(cube, mapper, metadata=self.metadata)

        key_attributes = []
        for dim in cube.dimensions:
            key_attributes += dim.key_attributes()

        if keys_only:
            statement = context.denormalized_statement(attributes=key_attributes, expand_locales=True)
        else:
            statement = context.denormalized_statement(expand_locales=True)

        schema = schema or self.options.get("denormalized_view_schema") or self.schema

        dview_prefix = self.options.get("denormalized_view_prefix","")
        view_name = view_name or dview_prefix + cube.name

        if mapper.fact_name == view_name and schema == mapper.schema:
            raise WorkspaceError("target denormalized view is the same as source fact table")

        table = sqlalchemy.Table(view_name, self.metadata,
                                 autoload=False, schema=schema)

        preparer = self.engine.dialect.preparer(self.engine.dialect)
        full_name = preparer.format_table(table)

        if table.exists():
            self._drop_table(table, schema, force=replace)

        if materialize:
            create_stat = "CREATE TABLE"
        else:
            create_stat = "CREATE OR REPLACE VIEW"

        statement = "%s %s AS %s" % (create_stat, full_name, str(statement))
        self.logger.info("creating denormalized view %s (materialized: %s)" \
                                            % (full_name, materialize))
        # print("SQL statement:\n%s" % statement)
        self.engine.execute(statement)

        if create_index:
            if not materialize:
                raise WorkspaceError("Index can be created only on a materialized view")

            # self.metadata.reflect(schema = schema, only = [view_name] )
            table = sqlalchemy.Table(view_name, self.metadata,
                                     autoload=True, schema=schema)
            self.engine.reflecttable(table)

            for attribute in key_attributes:
                label = attribute.ref()
                self.logger.info("creating index for %s" % label)
                column = table.c[label]
                name = "idx_%s_%s" % (view_name, label)
                index = sqlalchemy.schema.Index(name, column)
                index.create(self.engine)

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
                                schema=None, dimension_prefix=None, replace=False):
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
        * `replace` – if ``True`` then existing table will be replaced,
          otherwise an exception is raised if table already exists.
        """
        mapper = SnowflakeMapper(cube, cube.mappings, **self.options)
        context = QueryContext(cube, mapper, metadata=self.metadata)

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

        table_name = "%s%s_%s" % (dimension_prefix or "",
                                  str(dimension), str(level))
        self._create_table_from_statement(table_name, statement, schema,
                                            replace, insert=True)

    def create_conformed_rollups(self, cube, dimensions, grain=None, schema=None,
                                 dimension_prefix=None, replace=False):
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
                                    dimension_prefix=dimension_prefix,
                                    replace=replace)

    def _create_table_from_statement(self, table_name, statement, schema,
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
            new_col = sqlalchemy.Column(str(col), col.type)
            table.append_column(new_col)

        self.logger.info("creating table '%s'" % str(table))
        self.metadata.create_all(tables=[table])

        if insert:
            self.logger.debug("inserting into table '%s'" % str(table))
            insert_statement = InsertIntoAsSelect(table, statement,
                                                  columns=statement.columns)
            self.engine.execute(str(insert_statement))

        return table

    def create_cube_aggregate(self, cube, table_name=None, dimensions=None,
                                required_dimensions=None, schema=None,
                                replace=False):
        """Creates an aggregate table. If dimensions is `None` then all cube's
        dimensions are considered.

        Arguments:

        * `dimensions`: list of dimensions to use in the aggregated cuboid, if
          `None` then all cube dimensions are used
        * `required_dimensions`: list of dimensions that are required for each
          aggregation (for example a date dimension in most of the cases). The
          list should be a subsed of `dimensions`.
        * `aggregates_prefix`: aggregated table prefix
        * `aggregates_schema`: schema where aggregates are stored

        """

        schema = schema or self.options.get("aggregates_schema") or self.schema
        prefix = self.options.get("aggregates_prefix","")
        table_name = table_name or prefix + cube.name

        cube = self.model.cube(cube)
        dimensions = dimensions or cube.dimensions

        # Collect keys that are going to be used for aggregations
        keys = []
        for dimension in dimensions:
            keys += [level.key for level in dimension.hierarchy().levels]

        mapper = SnowflakeMapper(cube, cube.mappings, **self.options)
        context = QueryContext(cube, mapper, metadata=self.metadata)

        if mapper.fact_name == table_name and schema == mapper.schema:
            raise WorkspaceError("target is the same as source fact table")

        drilldown = {}

        for dim in dimensions:
            level = dim.hierarchy().levels[-1]
            drilldown[str(dim)] = level

        cell = Cell(cube)
        drilldown = coalesce_drilldown(cell, drilldown)

        # Create dummy statement of all dimension level keys for
        # getting structure for table creation
        statement = context.aggregation_statement(cell,
                                                  attributes=keys,
                                                  drilldown=drilldown)


        #
        # Create table
        #
        table = self._create_table_from_statement(table_name, statement,
                                schema=schema, replace=replace, insert=False)

        connection = self.engine.connect()

        cuboids = hierarchical_cuboids(dimensions,
                                        required=required_dimensions)

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

            dd = coalesce_drilldown(cell, dd)

            statement = context.aggregation_statement(cell,
                                                      attributes=keys,
                                                      drilldown=drilldown)
            self.logger.info("inserting")
            insert = InsertIntoAsSelect(table, statement,
                                  columns=statement.columns)
            connection.execute(str(insert))
