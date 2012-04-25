# -*- coding=utf -*-
import cubes.browser
from cubes.backends.sql.common import AttributeMapper, JoinFinder
from cubes.backends.sql.common import DEFAULT_KEY_FIELD
import logging
import sqlalchemy
import sqlalchemy.sql as sql

# Required functionality checklist
# 
# * [unfinished] fact
# * [ ] facts in a cell
# * [ ] number of items in drill-down
# * [ ] dimension values
# * [ ] drill-down sorting
# * [ ] drill-down pagination
# * [ ] drill-down limits (such as top-10)
# * [ ] facts sorting
# * [ ] facts pagination
# * [ ] dimension values sorting
# * [ ] dimension values pagination
# * [ ] remainder
# * [ ] ratio - aggregate sum(current)/sum(total) 
# * [ ] derived measures (should be in builder)

__all__ = ["StarBrowser"]

class StarBrowser(object):
    """docstring for StarBrowser"""
    
    def __init__(self, cube, connection=None, locale=None, dimension_prefix=None,
                fact_prefix=None, schema=None):
        """StarBrowser is a SQL-based AggregationBrowser implementation that 
        can aggregate star and snowflake schemas without need of having 
        explicit view or physical denormalized table.

        Attributes:
        
        * `cube` - browsed cube
        * `dimension_prefix` - prefix for dimension tables
        * `fact_prefix` - prefix for fact tables (`prefix`+`cube.name`)
        * `schema` - default database schema name
        * `locale` - locale used for browsing

        .. warning:
            
            Not fully implemented yet.

        **Limitations:**
        
        * only one locale can be used for browsing at a time
        * locale is implemented as denormalized: one column for each language
        """
        super(StarBrowser, self).__init__()

        if cube == None:
            raise Exception("Cube for browser should not be None.")

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        self.cube = cube
        self.dimension_prefix = dimension_prefix
        self.schema = schema

        self.mappings = cube.mappings
        
        self.locale = locale
        self.joinfinder = JoinFinder(cube, joins=cube.joins)
        self.tables = {}
        
        if connection is not None:
            self.connection = connection
            self.metadata = sqlalchemy.MetaData(bind=self.connection)

            fact_prefix = fact_prefix or ""
            self.fact_name = cube.fact or fact_prefix + cube.name
            self.fact_table = sqlalchemy.Table(self.fact_name, self.metadata, 
                                               autoload=True, schema=schema)

            # Register the fact table immediately
            self.tables[(self.schema, self.fact_name)] = self.fact_table
            self.fact_key = self.cube.key or DEFAULT_KEY_FIELD

        self.mapper = AttributeMapper(cube, self.mappings, self.locale, 
                                            schema=self.schema,
                                            fact_name=self.fact_name,
                                            dimension_prefix=dimension_prefix)

        self.joinfinder = JoinFinder(cube, joins=cube.joins, 
                                     fact_name=self.fact_name)

    
    def all_attributes(self):
        """Collect all cube attributes"""
        attributes = []
        attributes += self.cube.measures
        attributes += self.cube.details

        for dim in self.cube.dimensions:
            # attributes += dim.all_attributes()
            all_attributes = dim.all_attributes()
            for attr in all_attributes:
                if not attr.dimension:
                    raise Exception("No dimension in attr %s" % attr)
            attributes += all_attributes

        return attributes
    
    def to_physical(self, attributes):
        """Convert attributes to physical"""
        physical_attrs = []
        for attr in attributes:
            ref = self.mapper.physical(attr)
            physical_attrs.append(ref)
            self.logger.debug("physical: %s.%s -> %s" % (attr.dimension, attr, tuple(ref)))

    def fact(self, key_value):
        """Get the fact from cube."""

        # 1. get all fact attributes: key, measures, details
        attributes = self.all_attributes()
        
        # 2. Get physical references (schema, table, column)
        physical_references = []
        attribute_map = {}
        for attr in attributes:
            ref = self.mapper.physical(attr)
            physical_references.append(ref)
            attribute_map[attr] = ref
            self.logger.debug("physical: %s.%s -> %s" % (attr.dimension, attr, tuple(ref)))

        # 3. Collect relevant joins (all are relevant in this case)
        joins = self.joinfinder.relevant_joins(physical_references)
        
        # 4. Construct statement
        
        join_expression = self.create_join_expression(joins)
        
        # 5. Collect columns
        columns = []
        for attr in attributes:
            ref = attribute_map[attr]
            table = self.table(ref.schema, ref.table)
            column = table.c[ref.column]
            localized_alias = self.mapper.logical(attr)
            column.label(localized_alias)
            
            # return expression.label(localized_alias, column)
            columns.append(column)
            
        key_column = self.fact_table.c[self.fact_key]
        condition = key_column == key_value

        select = sql.expression.select(columns, 
                                    # whereclause = condition, 
                                    from_obj = join_expression,
                                    use_labels=True)

        print "SQL:\n%s" % select
        cursor = self.connection.execute(select)

        row = cursor.fetchone()

        if row:
            # Convert SQLAlchemy object into a dictionary
            record = dict(row.items())
        else:
            record = None
            
        return record

    def create_join_expression(self, joins):
        """Create basic SQL SELECT expression on a fact table with `joins`"""
        self.logger.info("create basic expression with %d joins" % len(joins))

        expression = self.fact_table
        
        for join in joins:
            self.logger.debug("join: %s" % (join, ))

            if not join.detail.table or join.detail.table == self.fact_name:
                raise ValueError("Detail table name should be present and should not be a fact table.")

            master_table = self.table(join.master.schema, join.master.table)
            detail_table = self.table(join.detail.schema, join.detail.table, join.alias)

            try:
                master_column = master_table.c[join.master.column]
            except:
                raise Exception('Unable to find master key (schema %s) "%s"."%s" ' \
                                    % join.master)
            try:
                detail_column = detail_table.c[join.detail.column]
            except:
                raise Exception('Unable to find detail key (schema %s) "%s"."%s" ' \
                                    % join.detail)

            onclause = master_column == detail_column

            expression = sql.expression.join(expression,
                                                    detail_table,
                                                    onclause=onclause)
        return expression
            
        
    def table(self, schema, table_name, alias=None):
        """Return a SQLAlchemy Table instance. If table was already accessed,
        then existing table is returned. Otherwise new instance is created.
        
        If `schema` is ``None`` then browser's schema is used. If `table_name`
        is ``None``, then fact table is used.
        """

        # table_name = table_name or self.fact_name
        aliased_name = alias or table_name
        table_ref = (schema or self.schema, aliased_name)
        if table_ref in self.tables:
            return self.tables[table_ref]
        
        table = sqlalchemy.Table(table_name, self.metadata, 
                                 autoload=True, schema=schema)

        self.logger.debug("registering table '%s' as '%s'" % (table_name, aliased_name))
        if alias:
            table = table.alias(alias)
            
        self.tables[table_ref] = table
        return table
        
    def aggregate(self, cell, measures = None, drilldown = None, details = False, **options):
        pass

def create_workspace(model, config):
    """Create workspace for `model` with configuration in dictionary `config`. 
    This method is used by the slicer server."""

    try:
        dburl = config["url"]
    except KeyError:
        raise Exception("No URL specified in configuration")

    schema = config.get("schema")
    dimension_prefix = config.get("dimension_prefix")
    fact_prefix = config.get("fact_prefix")

    engine = sqlalchemy.create_engine(dburl)

    workspace = SQLStarWorkspace(model, engine, schema, 
                                    dimension_prefix = dimension_prefix,
                                    fact_prefix = fact_prefix)

    return workspace

class SQLStarWorkspace(object):
    """Factory for browsers"""
    def __init__(self, model, engine, schema=None, dimension_prefix=None, 
                 fact_prefix=None):
        """Create a workspace"""
        super(SQLStarWorkspace, self).__init__()
        self.model = model
        self.engine = engine
        self.metadata = sqlalchemy.MetaData(bind = self.engine)
        self.dimension_prefix = dimension_prefix
        self.fact_prefix = fact_prefix
        self.schema = schema

    def browser_for_cube(self, cube, locale=None):
        """Creates, configures and returns a browser for a cube"""

        # TODO(Stiivi): make sure that we are leaking connections here
        cube = self.model.cube(cube)
        browser = StarBrowser(cube, self.engine.connect(), locale=locale,
                                dimension_prefix=self.dimension_prefix,
                                fact_prefix=self.fact_prefix,
                                schema=self.schema)
        return browser
