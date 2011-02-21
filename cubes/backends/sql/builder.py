import logging
import sets
import cubes.model as model

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
        for attribute in self.cube.measures:
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
            full_name = dim.name + "." + attribute
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
        for attribute in self.cube.measures:
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
        split = field.split('.')
        if len(split) > 1:
            table_name = split[0]
            field_name = ".".join(split[1:])
            return (table_name, field_name)
        else:
            return (None, field)

    def join_field(self, table, field):
        return table + "." + field
        
    def validate(self):
        """Validates cube, whether its specification is suficient for view creation.
        """
        pass
        
    def quote_field(self, field):
        """Quote field name"""
        return '"%s"' % field
