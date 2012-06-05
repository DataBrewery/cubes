import logging
import sets
import cubes.model as model
from mapper import DEFAULT_KEY_FIELD
try:
    import sqlalchemy
    import sqlalchemy.sql.expression as expression
    import sqlalchemy.sql.functions as function
except:
    pass

import collections
    
__all__ = [
    "SQLDenormalizer"
]    

Attribute = collections.namedtuple("Attribute", "attribute, alias, dimension, locales")

class SQLDenormalizer(object):
    """Star/Snowflake schema denormalizer, uses SQL alchemy"""
    
    capabilities = ["localization"]
    
    def __init__(self, cube, connection = None, schema = None, dimension_table_prefix = None):
        """Creates a simple SQL view builder.
        
        :Parameters:
            * `cube` - cube from logical model
            * `connection` - database connection, default None if you want only to create SELECT statement
            * `dimension_table_prefix` - default prefix for dimension tables - used if there is no
              mapping for dimension attribute. Say you have dimension `supplier` and field `name` and
              dimension table prefix ``dm_`` then default physical mapping for that field would be:
              ``dm_supplier.name``
        
        """
        if not cube:
            raise ValueError("Cube should be not null")
            
        self.expression = None
        
        self.cube = cube
        self.select_statement = None
        self.field_names = []
        self.table_aliases = {}
        self.schema = schema
        self.tables = {}
        
        self.logger = logging.getLogger(__name__)

        # Use fact table name from model specification. If there is no fact specified, we assume
        # that the fact table has same name as cube.
        if self.cube.fact:
            self.fact_name = self.cube.fact
        else:
            self.fact_name = self.cube.name

        self.fact_alias = "__f"
        self.cube_key = self.cube.key

        if not self.cube_key:
            self.cube_key = DEFAULT_KEY_FIELD

        self.cube_attributes = [ self.cube_key ]
        for measure in self.cube.measures:
            # print "APPENDING MEASURE: %s: %s" % (measure, str(measure))
            self.cube_attributes.append(str(measure))
        
        self.dimension_table_prefix = dimension_table_prefix
     
        if connection:
            self.connection = connection
            self.engine = self.connection.engine
            self.metadata = sqlalchemy.MetaData()
            self.metadata.bind = self.engine
            self.metadata.reflect()
            try:
                self.fact_table = self._table(self.fact_name, schema = self.schema)
            except Exception as e:
                raise Exception("Unable to find fact table '%s' (reason: %s)" % 
                                    (self.fact_name, str(e)) )
        else:
            self.connection = None
            self.engine = None
            self.fact = None

    def denormalized_view(self):
        """Returns SQLAlchemy expression representing select from denormalized view."""
        
        if not self.expression:
            self._create_view_expression()

        return self.expression
        
    def _create_view_expression(self):
        """Creates a view expression - SQLAlchemy expression statement.
        """

        self.expression = None
        
        self.index_attributes = []

        self._collect_attributes()
        self._collect_joins()
        self._collect_columns()

        self.expression = expression.select(self.columns, from_obj = self.expression)

        # self.logger.debug("SQL:\n%s" % str(self.sexpression))
        # count = self.connection.execute(selection).rowcount
        # self.logger.info("rows: %d" % count)
        # self.logger.info("rows: %d" % self.connection.execute(self.fact_table.select()).rowcount)
    
    def create_view(self, view_name, schema=None, index=False, materialize=True):
        """Creates a view.

        :Arguments:
            * `view_name` - name of a view or a table to be created
            * `schema` - target database schema
            * `index` - create indexes on level key columns if ``True``. default ``False``
            * `materialize` - create materialized view (currently as table) if ``True`` (default)
        """
        if not self.expression:
            self._create_view_expression()

        table = self._table(view_name, schema = schema, autoload = False)
        if materialize and table.exists():
            table.drop(checkfirst=False)

        full_view_name = schema + "." + view_name if schema else view_name

        if materialize:
            create_statement = "CREATE TABLE"
        else:
            create_statement = "CREATE OR REPLACE VIEW"

        statement = "%s %s AS %s" % (create_statement, full_view_name, str(self.expression))
        self.logger.info("creating table %s" % full_view_name)
        self.logger.debug("SQL statement: %s" % statement)
        self.connection.execute(statement)

        if index:
            # self.metadata.reflect(schema = schema, only = [view_name] )
            table = self._table(view_name, schema = schema, autoload = True)
            self.engine.reflecttable(table)

            for attribute in self.index_attributes:
                self.logger.info("creating index for %s" % attribute.alias)
                column = table.c[attribute.alias]
                name = "idx_%s_%s" % (view_name, attribute.alias)
                index = sqlalchemy.schema.Index(name, column)
                index.create(self.engine)
                
    def _collect_attributes(self):
        """Collect all attributes from model and create mappings from logical to physical
        representation
        """

        self.logger.info("collecting fact attributes (key, mesures and details)...")

        # self.attributes contains tuples: attribute, dimension
        key_attribute = Attribute(self.cube_key, str(self.cube_key), None, None)
        self.attributes = [ key_attribute ]
        self.index_attributes = [ key_attribute ]

        for attribute in self.cube.measures:
            self.attributes.append( Attribute(attribute.name, str(attribute.name), None, None) )

        for attribute in self.cube.details:
            self.attributes.append( Attribute(attribute.name, str(attribute.name), None, None) )
            
        # FIXME: refactor this
        for dim in self.cube.dimensions:
            # Treat flat dimensions with no hierarchies differently here
            if dim.is_flat and not dim.has_details:
                attr = Attribute(dim.name, str(dim.name), None, None)
                self.attributes.append(attr)
                self.index_attributes.append(attr)
            else:
                hier = dim.default_hierarchy
                for level in hier.levels:
                    for attribute in level.attributes:
                        # FIXME: add localization
                        alias = attribute.ref()
                        obj = Attribute(attribute, alias, dim, attribute.locales)
                        self.attributes.append(obj)

                        if attribute.name == level.key:
                            self.index_attributes.append(obj)

    def _collect_joins(self):
        """Collect joins and register joined tables. All tables used should be collected in this
        function."""

        self.logger.info("collecting joins and registering tables...")

        self.tables = {}
        self.expression = self.fact_table
        self.tables[self.fact_name] = self.fact_table

        if not self.cube.joins:
            self.logger.info("no joins")
            return

        for join in self.cube.joins:
            self.logger.debug("join: %s" % join)

            # Get master and detail table names and their respective keys that will be used for join
            master_name, master_key = self.split_field(join["master"])
            if not master_name:
                master_name = self.fact_name
                
            detail_name, detail_key = self.split_field(join["detail"])
            alias = join.get("alias")

            if not detail_name or detail_name == self.fact_name:
                raise ValueError("Detail table name should be present and should not be a fact table")

            master_table = self.table(master_name)
            detail_table = self.register_table(detail_name, alias = alias, schema = self.schema)

            try:
                master_column = master_table.c[master_key]
            except:
                raise Exception('Unable to find master key "%s"."%s" ' % (master_name, master_key))
            try:
                detail_column = detail_table.c[detail_key]
            except:
                raise Exception('Unable to find master key "%s"."%s" ' % (detail_name, detail_key))

            onclause = master_column == detail_column

            self.expression = expression.join(self.expression, detail_table, onclause = onclause)

    def _collect_columns(self):
        """Collect selected columns
        
        Rules:
            * dimension field is mapped as "dimname.attribute"
            * fact field is mapped as "attribute"
        
        """
        self.logger.info("building mappings...")
        # self.mappings = {}

        self.columns = []
        
        for attribute in self.attributes:
            if attribute.locales:
                for locale in attribute.locales:
                    self.columns.append(self._select_column(attribute, locale))
            else:
                self.columns.append(self._select_column(attribute))
                
    def _select_column(self, attribute, locale = None):
        """get select column"""
        
        if locale:
            localized_alias = attribute.alias + "." + locale
        else:
            localized_alias = attribute.alias

        if self.dimension_table_prefix:
            prefix = self.dimension_table_prefix
        else:
            prefix = ""
        self.logger.debug("looking for mapping %s (%s)" % (localized_alias, attribute.alias))

        if self.cube.mappings and localized_alias in self.cube.mappings:
            mapping = self.cube.mappings[localized_alias]
            original_mapping = mapping
            self.logger.debug("  is in mappings: %s" % mapping)
        elif self.cube.mappings and attribute.alias in self.cube.mappings:
            mapping = self.cube.mappings[attribute.alias]
            original_mapping = mapping
            self.logger.debug("  not in mappings, using default trans: %s" % mapping)
        else:
            original_mapping = None
            if attribute.dimension:
                mapping = prefix + attribute.alias
            else:
                mapping = attribute.alias

            # FIXME: make this work
            if locale:
                mapping = mapping + "_" + locale
                
            self.logger.debug("  defaulting to: %s" % mapping)

        (table_name, field_name) = self.split_field(mapping)
        if not table_name:
            table_name = self.fact_name
            
        table = self.table(table_name)

        try:
            column = table.c[field_name]
        except KeyError:
            raise model.ModelError("Mapped column '%s' does not exist (as %s.%s)" \
                                        % (localized_alias, table_name, field_name) )
        
        self.logger.debug("adding column %s as %s" % (column, localized_alias))
        # self.mappings[localized_alias] = column
        return expression.label(localized_alias, column)
            
    def split_field(self, field):
        """Split field into table and field name: before first '.' is table name, everything else
        is field name. If there is no '.', then table name is None."""
        split = str(field).split('.')
        if len(split) > 1:
            table_name = split[0]
            field_name = ".".join(split[1:])
            return (table_name, field_name)
        else:
            return (None, field)
    
    def table(self, table_name):
        """Get a table with name `table_name`. If table was not yet collected (while collecting joins)
        then raise an exception. If `alias` is specified, then table will be registered as known under
        that alias."""
        if table_name not in self.tables:
            raise Exception("Table '%s' not registered within joins" % table_name)
        else:
            return self.tables[table_name]

    def register_table(self, table_name, alias, schema = None):

        if (alias and alias in self.tables) or (table_name in self.tables):
            raise Exception("Table '%s' (alias '%s') already registere" % (table_name, alias))

        table = self._table(table_name, schema = schema)
        if alias:
            table = table.alias(alias)
            register_name = alias
        else:
            register_name = table_name

        self.logger.debug("registering table '%s' as '%s'" % (table_name, register_name))
        self.tables[register_name] = table
        return table
        
    def _table(self, table_name, schema = None, autoload = True):
        table = sqlalchemy.Table(table_name, self.metadata, 
                                     autoload = autoload, 
                                     schema = schema)
        return table
