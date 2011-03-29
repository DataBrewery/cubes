import logging
import sets
import cubes.model as model
import base
try:
    import sqlalchemy
    import sqlalchemy.sql.expression as expression
    import sqlalchemy.sql.functions as function
except:
    pass

import collections
    
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
            
        self.cube = cube
        self.select_statement = None
        self.field_names = []
        self.table_aliases = {}
        self.schema = schema
        
        self.logger = logging.getLogger("brewery.cubes")

        # Use fact table name from model specification. If there is no fact specified, we assume
        # that the fact table has same name as cube.
        if self.cube.fact:
            self.fact_name = self.cube.fact
        else:
            self.fact_name = self.cube.name

        self.fact_alias = "__f"
        self.cube_key = self.cube.key

        if not self.cube_key:
            self.cube_key = base.DEFAULT_KEY_FIELD

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
            self.fact_table = self._table(self.fact_name, self.schema)
        else:
            self.connection = None
            self.engine = None
            self.fact = None
            
    def create_materialized_view(self, view_name, schema = None):
        self.expression = None

        self._collect_attributes()
        self._collect_joins()
        self._collect_columns()

        selection = expression.select(self.columns, from_obj = self.expression)
        self.logger.debug("SQL:\n%s" % str(selection))

        # count = self.connection.execute(selection).rowcount
        # self.logger.info("rows: %d" % count)
        # self.logger.info("rows: %d" % self.connection.execute(self.fact_table.select()).rowcount)
    
        table = self._table(view_name, schema = schema, autoload = False)
        if table.exists():
            table.drop(checkfirst=False)

        full_view_name = schema + "." + view_name if schema else view_name
        statement = "CREATE TABLE %s AS %s" % (full_view_name, str(selection))
        self.logger.info("creating table %s" % full_view_name)
        self.logger.debug("SQL statement: %s" % statement)
        self.connection.execute(statement)

    def _collect_attributes(self):
        """Collect all attributes from model and create mappings from logical to physical representation
        """
        self.logger.info("collecting fact attributes...")

        # self.attributes contains tuples: attribute, dimension
        self.attributes = [ Attribute(self.cube_key, str(self.cube_key), None, None) ]

        for attribute in self.cube.measures:
            self.attributes.append( Attribute(attribute.name, str(attribute.name), None, None) )

        self.logger.info("collecting dimension attributes...")

        for dim in self.cube.dimensions:
            hier = dim.default_hierarchy
            for level in hier.levels:
                for attribute in level.attributes:
                    # FIXME: add localization
                    alias = attribute.full_name(dim)
                    self.attributes.append( Attribute(attribute, alias, dim, attribute.locales) )

    def _collect_joins(self):
        self.logger.info("collecting joins...")

        self.expression = self.fact_table
        
        for join in self.cube.joins:
            self.logger.debug("join: %s" % join)
            
            master_name, master_key = self.split_field(join["master"])
            detail_name, detail_key = self.split_field(join["detail"])

            if not detail_name or detail_name == self.fact_name:
                raise ValueError("Detail should not be a fact table")

            master_table = self._table(master_name, self.schema) if master_name else self.fact_table
            detail_table = self._table(detail_name, self.schema)
            
            master_column = master_table.c[master_key]
            detail_column = detail_table.c[detail_key]
            
            onclause = master_column == detail_column
            print onclause
            self.expression = expression.join(self.expression, detail_table, onclause = onclause)

    def _collect_columns(self):
        """Collect selected columns
        
        Rules:
            * dimension field is mapped as "dimname.attribute"
            * fact field is mapped as "attribute"
        
        """
        self.logger.info("building mappings...")
        self.mappings = {}

        self.columns = []
        
        for attribute in self.attributes:
            if attribute.locales:
                for locale in attribute.locales:
                    self._select_attribute(attribute, locale)
            else:
                self._select_attribute(attribute)
                
    def _select_attribute(self, attribute, locale = None):

        if locale:
            localized_alias = attribute.alias + "." + locale
        else:
            localized_alias = attribute.alias

        if self.dimension_table_prefix:
            prefix = self.dimension_table_prefix
        else:
            prefix = ""
        self.logger.debug("looking for mapping %s" % (localized_alias))

        if localized_alias in self.cube.mappings:
            mapping = self.cube.mappings[localized_alias]
            original_mapping = mapping
            self.logger.debug("  is in mappings: %s" % mapping)
        elif attribute.alias in self.cube.mappings:
            mapping = self.cube.mappings[attribute.alias]
            original_mapping = mapping
            self.logger.debug("  not in mappings, using default trans: %s" % mapping)
        else:
            original_mapping = None
            if attribute.dimension:
                mapping = prefix + attribute.alias
            else:
                mapping = attribute.alias
            self.logger.debug("  defaulting to: %s" % mapping)

        (table_name, field_name) = self.split_field(mapping)
        table = self._table(table_name, self.schema) if table_name else self.fact_table
        try:
            column = table.c[field_name]
        except KeyError:
            raise model.ModelError("Mapped column '%s' for fact attribute '%s'"
                                   " does not exist" % (original_mapping, attribute.alias) )
        
        self.logger.debug("adding column %s as %s" % (column, localized_alias))
        self.mappings[localized_alias] = column
        self.columns.append(expression.label(localized_alias, column))
            
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
        
    def _table(self, table_name, schema = None, autoload = True):
        table = sqlalchemy.Table(table_name, self.metadata, 
                                     autoload = autoload, 
                                     schema = schema)
                                
        return table
        
class SimpleSQLBuilder(object):
    """Create denormalized SQL views based on logical model. The views are used by SQL aggregation browser
    (query generator)"""
    
    def __init__(self, cube, connection = None, dimension_table_prefix = None):
        """Creates a simple SQL view builder.
        
        :Parameters:
            * `cube` - cube from logical model
            * `connection` - database connection, default None if you want only to create SELECT statement
            * `dimension_table_prefix` - default prefix for dimension tables - used if there is no
              mapping for dimension attribute. Say you have dimension `supplier` and field `name` and
              dimension table prefix ``dm_`` then default physical mapping for that field would be:
              ``dm_supplier.name``
        
        """
        self.cube = cube
        self.select_statement = None
        self.field_names = []
        self.table_aliases = {}
        
        self.connection = connection

        self.logger = logging.getLogger("brewery.cubes")

        # Use fact table name from model specification. If there is no fact specified, we assume
        # that the fact table has same name as cube.
        if self.cube.fact:
            self.fact_table = self.cube.fact
        else:
            self.fact_table = self.cube.name

        self.fact_alias = "f"
        self.cube_key = self.cube.key

        if not self.cube_key:
            self.cube_key = base.DEFAULT_KEY_FIELD

        self.cube_attributes = [ self.cube_key ]
        for measure in self.cube.measures:
            print "APPENDING MEASURE: %s: %s" % (measure, str(measure))
            self.cube_attributes.append(str(measure))
        
        self.dimension_table_prefix = dimension_table_prefix
     
    def create_view(self, view_name):
        """Create a denormalized SQL view.

        Args:
            * view_name: name of a view to be created
        """

        self.create_select_statement()
        statement = "CREATE OR REPLACE VIEW %s AS \n%s" % (view_name, self.select_statement)
        self.view_statement = statement
        self.connection.execute(statement)

    def create_materialized_view(self, view_name):
        """Create materialized view (a fact table) of denormalized cube structure. Materialized
        views are faster than normal views as there are no joins involved.

        Args:
            * view_name: name of a view (table) to be created
        """

        self.create_select_statement()

        statement = "DROP TABLE IF EXISTS %s" % view_name
        self.connection.execute(statement)

        statement = "CREATE TABLE %s AS %s" % (view_name, self.select_statement)
        self.connection.execute(statement)

    def create_select_statement(self):
        """
        Algorithm:
        
        #. collect all attributes from measures, dimension levels and joins
        #. build mappings for attributes
        #. collect all tables from mappings and create table aliases
        #. create mappings using table aliases (not physical tables)
        #. collect all joins and create `join expression`
        #. create `select expression`
        #. create `select statement` from `select expression` and `join expression` 
        
        """
        #  5. ...
        # 10. prepare joins
        # 20. collect selected fields
        self.logger.info("Creating SQL statement")
        
        self._collect_attributes()
        self._build_attribute_mappings()
        self._collect_tables()
        self._remap_aliased()
        self._collect_joins()
        self._collect_selection()
        
        expressions = [
                        "SELECT", 
                        self.select_expression,
                        "FROM %s AS %s" % (self.fact_table, self.table_aliases[self.fact_table]),
                        self.join_expression
                      ]
        self.select_statement = "\n".join(expressions)
        
        pass
    
    def _collect_attributes(self):
        """Collect all attributes from model and create mappings from logical to physical representation
        """
        self.logger.info("collecting fact attributes...")
        self.fact_attributes = []
        for attribute in self.cube_attributes:
            self.fact_attributes.append(attribute)
        self.logger.debug("found: %s" % self.fact_attributes)

        self.logger.info("collecting dimension attributes...")
        self.dim_attributes = []
        for dim in self.cube.dimensions:
            hier = dim.default_hierarchy
            for level in hier.levels:
                for attribute in level.attributes:
                    self.dim_attributes.append( (dim, attribute) )
        
        self.logger.debug("found: %s" % self.dim_attributes)

        self.logger.info("collecting join attributes...")
        for join in self.cube.joins:
            for attribute in (join["master"], join["detail"]):
                (table, field) = self.split_field(attribute)
                if not table or table == "fact":
                    if not field in self.fact_attributes:
                        self.fact_attributes.append(field)
                else:
                    dim = self.cube.dimension(table)
                    obj = (dim, field)
                    if obj not in self.dim_attributes:
                        self.dim_attributes.append(obj)

    def _build_attribute_mappings(self):
        """Create mappings for attribute -> physical field
        
        Rules:
            * dimension field is mapped as dimname.attribute
            * fact field is mapped as fact.attribute
        
        """
        self.logger.info("building mappings...")
        self.mappings = {}

        if self.dimension_table_prefix:
            prefix = self.dimension_table_prefix
        else:
            prefix = ""
        
        for dim_attr in self.dim_attributes:
            dim, attribute = dim_attr
            full_name = dim.name + "." + str(attribute)
            if full_name in self.cube.mappings:
                mapping = self.cube.mappings[full_name]
            else:
                mapping = prefix + full_name

            if full_name in self.mappings:
                raise model.ModelError("Dimension attribute '%s' is specified more than once", full_name)

            self.mappings[full_name] = mapping
            self.logger.debug("dim map: %s -> %s" % (full_name, mapping))

        for name in self.fact_attributes:
            (table, field) = self.split_field(name)

            full_field = self.join_field("fact", field)
            if field in self.cube.mappings:
                mapping = self.cube.mappings[field]
            elif full_field in self.cube.mappings:
                mapping = self.cube.mappings[full_field]
            else:   
                mapping = self.join_field(self.fact_table, field)
                
            if full_field in self.mappings:
                raise model.ModelError("Fact measure '%s' is specified more than once", name)

            self.mappings[full_field] = mapping
            self.logger.debug("fact map: %s -> %s" % (full_field, mapping))
    
    def _collect_tables(self):
        """Collect all tables that we are going to consider"""
        self.logger.info("collecting tables...")
        self.logger.debug("mappings: %s" % self.mappings)
        
        self.tables = set([self.fact_table])
        for mapping in self.mappings.values():
            table = self.split_field(mapping)[0]
            if table:
                self.logger.debug("found mapping table: '%s'" % (table))
                self.tables.add(table)
        
        self.table_aliases = {}
        self.table_aliases[self.fact_table] = self.fact_alias

        index = 1
        for table in self.tables:
            if table not in self.table_aliases:
                self.table_aliases[table] = "d%d" % index
                index += 1
            
        for table, alias in self.table_aliases.items():
            self.logger.debug("found table: '%s' alias '%s'" % (table, alias))

    def _remap_aliased(self):
        """Since we can not refer to tables by their names in SELECT statement, we have to alias them.
        Mappings refer to real table names - we need to change real table name to generated table
        alias."""
        
        self.logger.info("realiasing...")

        self.aliased_mappings = {}
        for (field, mapping) in self.mappings.items():
            (table, column) = self.split_field(mapping)
            if table:
                alias = self.table_aliases[table]
                aliased_mapping = self.join_field(alias, column)
            else:
                aliased_mapping = self.join_field(self.fact_alias, column)
            self.aliased_mappings[field] = aliased_mapping

        for old, new in self.aliased_mappings.items():
            self.logger.debug("realiased: '%s' to '%s'" % (old, new))

    def _collect_joins(self):
        self.logger.info("collecting joins")
        expressions = []
        for join in self.cube.joins:
            master = join["master"]
            detail = join["detail"]
            
            # if master not in self.aliased_mappings:
            #     raise model.ModelError("Trying to join with unknown master attribute '%s'" % master)
            # if detail not in self.aliased_mappings:
            #     raise model.ModelError("Trying to join with unknown detail attribute '%s'" % detail)

            detail_mapping = self.mapping(detail)
            master_mapping = self.mapping(master)
            self.logger.debug("master mapping: %s for %s" % (master_mapping, master))

            detail_alias = self.split_field(detail_mapping)[0]
            detail_table = self.split_field(self.mapping(detail, aliased = False))[0]

            if not detail_table:
                detail_table = self.fact_table
            
            expr = "JOIN %s AS %s ON (%s = %s)" % (detail_table, detail_alias, 
                                                   detail_mapping, master_mapping)
            expressions.append(expr)
            self.logger.debug("join: %s", expr)

        self.join_expression = "\n".join(expressions)

    def _collect_selection(self):
        self.logger.info("collecting selection")
        expressions = []
        self.selected_fields = []
        for attribute in self.cube_attributes:
            mapping = self.mapping(attribute)
            expr = "%s AS %s" % (mapping, self.quote_field(attribute))
            expressions.append(expr)
            self.selected_fields.append(attribute)
            self.logger.debug("select: %s" % expr)

        for dim in self.cube.dimensions:
            hier = dim.default_hierarchy
            for level in hier.levels:
                for attribute in level.attributes:
                    full_name = self.join_field(dim.name, attribute)
                    mapping = self.mapping(full_name)
                    expr = "%s AS %s" % (mapping, self.quote_field(full_name))
                    expressions.append(expr)
                    self.selected_fields.append(full_name)
                    self.logger.debug("select: %s" % expr)

        self.select_expression = ",\n".join(expressions)

    def mapping(self, attribute, aliased = True):
        (table, field) = self.split_field(attribute)
        if not table:
            table = "fact"
        full_name = self.join_field(table, field)

        if aliased:
            mappings = self.aliased_mappings
        else:
            mappings = self.mappings

        if full_name not in mappings:
            raise model.ModelError("Unknown attribute '%s'" % full_name)
        return mappings[full_name]
                
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

    def join_field(self, table, field):
        return table + "." + str(field)
        
    def validate(self):
        """Validates cube, whether its specification is suficient for view creation.
        """
        pass
        
    def quote_field(self, field):
        """Quote field name"""
        return '"%s"' % field
