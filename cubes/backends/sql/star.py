# -*- coding=utf -*-
import cubes.browser
from cubes.backends.sql.common import Mapper
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

# Browsing context:
#     * engine
#     * metadata
#
#     * locale
#
#     * fact name
#     * dimension table prefix
#     * schema

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

        self.mapper = Mapper(cube, self.mappings, self.locale, 
                                            schema=self.schema,
                                            fact_name=self.fact_name,
                                            dimension_prefix=dimension_prefix,
                                            joins=cube.joins)
    
    def all_attributes(self):
        """Collect all cube attributes"""
        
        # FIXME: does not respect multiple hierarchies
        
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

        return physical_attrs

    def denormalized_statement(self, whereclause=None):
        """Return expression for denormalized view. """

        # 1. get all fact attributes: key, measures, details and their 
        # physical references (schema, table, column)
        attributes = self.all_attributes()
        physical_references = self.to_physical(attributes)

        joins = self.mapper.relevant_joins(physical_references)
        join_expression = self.create_join_expression(joins)
        
        # 4. Collect columns
        columns = []
        for attr, ref in zip(attributes, physical_references):
            table = self.table(ref.schema, ref.table)
            
            column = table.c[ref.column]
            localized_alias = self.mapper.logical(attr)
            column.label(localized_alias)
            
            # return expression.label(localized_alias, column)
            columns.append(column)
            

        select = sql.expression.select(columns, 
                                    whereclause=whereclause, 
                                    from_obj=join_expression,
                                    use_labels=True)

        return select
        
    def fact(self, key_value):
        """Get a single fact with key `key_value` from cube."""

        key_column = self.fact_table.c[self.fact_key]
        condition = key_column == key_value
        select = self.denormalized_statement(whereclause=condition)
        
        self.logger.debug("fact SQL:\n%s" % select)
        cursor = self.connection.execute(select)

        row = cursor.fetchone()

        if row:
            # Convert SQLAlchemy object into a dictionary
            record = dict(row.items())
        else:
            record = None
            
        return record

    def facts(self, cell, order=None, page=None, page_size=None):
        """Return all facts from `cell`, might be ordered and paginated."""
        
        # TODO: we might not have all tables available at this point
        # TODO: add conditions (we need separate query class as we
        #       need to collect more attributes and therefore tables
        #       and therefore joins)

        condition = self.conditions_for_cell(cell)
        statement = self.denormalized_statement(whereclause=condition)

        if page is not None and page_size is not None:
            statement = statement.offset(page * page_size).limit(page_size)

        self.logger.debug("facts SQL:\n%s" % statement)
        result = self.engine.execute(statement)

        return FactsIterator(result)

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

        attributes = self.all_attributes()
        physical_references = self.to_physical(attributes)

        # tables 

        # TODO: implement this
        raise NotImplementedError

        # tables = {}
        # 
        # for join in joins:
        #     self.logger.debug("join: %s" % (join, ))
        # 
        #     if not join.detail.table or join.detail.table == self.fact_name:
        #         raise ValueError("Detail table name should be present and should not be a fact table.")
        # 
        #     master_table = self.table(join.master.schema, join.master.table)
        #     detail_table = self.table(join.detail.schema, join.detail.table, join.alias)
        # 

    def aggregate(self, cell, measures = None, drilldown = None, details = False, **options):
        pass

class FactsIterator(object):
    """
    Iterator that returns SQLAlchemy ResultProxy rows as dictionaries
    """
    def __init__(self, result):
        self.result = result
        self.batch = None

    def __iter__(self):
        return self

    def next(self):
        if not self.batch:
            many = self.result.fetchmany()
            if not many:
                raise StopIteration
            self.batch = deque(many)

        row = self.batch.popleft()

        return dict(row.items())

class DenormalizedQuery(object):
    """docstring for DenormalizedQuery"""
    def __init__(self, arg):
        super(DenormalizedQuery, self).__init__()
        self.arg = arg
        
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
