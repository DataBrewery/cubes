# -*- coding=utf -*-
import cubes.browser
from cubes.backends.sql.common import Mapper
from cubes.backends.sql.common import DEFAULT_KEY_FIELD
import logging
import sqlalchemy
import sqlalchemy.sql as sql
import collections

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

        self.logger = cubes.common.get_logger()

        self.cube = cube

        self.locale = locale
        
        if connection is not None:
            self.connection = connection
            self.metadata = sqlalchemy.MetaData(bind=self.connection)

            fact_prefix = fact_prefix or ""
            self.fact_name = cube.fact or fact_prefix + cube.name

            # Register the fact table immediately
            self.fact_key = self.cube.key or DEFAULT_KEY_FIELD

        self.mapper = Mapper(cube, cube.mappings, self.locale, 
                                            schema=schema,
                                            fact_name=self.fact_name,
                                            dimension_prefix=dimension_prefix,
                                            joins=cube.joins)

        self.query = StarQueryBuilder(self.cube, self.mapper, 
                                      metadata=self.metadata)
    
    def fact(self, key_value):
        """Get a single fact with key `key_value` from cube."""

        key_column = self.query.fact_table.c[self.fact_key]
        condition = key_column == key_value

        select = self.query.denormalized_statement(whereclause=condition)
        
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
        
        # TODO: add ordering (ORDER BY)

        result = self.query.conditions_for_cell(cell)
        statement = self.query.denormalized_statement(whereclause=result.condition)

        if page is not None and page_size is not None:
            statement = statement.offset(page * page_size).limit(page_size)

        self.logger.debug("facts SQL:\n%s" % statement)
        result = self.engine.execute(statement)

        return FactsIterator(result)

    def aggregate(self, cell, measures = None, drilldown = None, details = False, **options):
        pass

    def validate(self):
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
        
        # Check joins

        tables = set()
        aliases = set()
        alias_map = {}
        # 
        for join in self.mapper.joins:
            self.logger.debug("join: %s" % (join, ))
        
            if not join.master.column:
                issues.append(("join", "master column not specified", join))
            if not join.detail.table:
                issues.append(("join", "detail table not specified", join))
            elif join.detail.table == self.fact_name:
                issues.append(("join", "detail table should not be fact table", join))
        
            master_table = (join.master.schema, join.master.table)
            tables.add(master_table)

            detail_alias = (join.detail.schema, join.alias or join.detail.table)

            if detail_alias in aliases:
                issues.append(("join", "duplicate detail table %s" % detail_table, join))
            else:
                aliases.add(detail_alias)
                
            detail_table = (join.detail.schema, join.detail.table)
            alias_map[detail_alias] = detail_table

            if detail_table in tables and not join.alias:
                issues.append(("join", "duplicate detail table %s (no alias specified)" % detail_table, join))
            else:
                tables.add(detail_table)
        
        # Check for existence of joined tables:
        physical_tables = {}
        
        for table in tables:
            try:
                physical_table = sqlalchemy.Table(table[1], self.metadata, 
                                        autoload=True, 
                                        schema=table[0] or self.mapper.schema)
                physical_tables[(table[0] or self.mapper.schema, table[1])] = physical_table
            except sqlalchemy.exc.NoSuchTableError:
                issues.append(("join", "table %s.%s does not exist" % table, join))
                
        # Check attributes
        
        attributes = self.mapper.all_attributes()
        physical = self.mapper.map_attributes(attributes)
        
        for attr, ref in zip(attributes, physical):
            table_ref = (ref.schema, ref.table)
            table = physical_tables.get(table_ref)
            if table is None:
                issues.append(("attribute", "table %s.%s does not exist for attribute %s" % (table_ref[0], table_ref[1], self.mapper.logical(attr)), attr))
            else:
                try:
                    c = table.c[ref.column]
                except KeyError:
                    issues.append(("attribute", "column %s.%s.%s does not exist for attribute %s" % (table_ref[0], table_ref[1], ref.column, self.mapper.logical(attr)), attr))
                
        return issues
        
"""Set of conditions. `attributes` - list of attributes involved in the conditions,
`conditions` - SQL conditions, `group_by` - attributes to be grouped by."""
ConditionSet = collections.namedtuple("ConditionSet",
                                    ["attributes", "conditions", "group_by"])


class StarQueryBuilder(object):
    """StarQuery"""
    def __init__(self, cube, mapper, metadata):
        """Object representing queries to the star. `mapper` is used for
        mapping logical to physical attributes and performing joins.
        `metadata` is a `sqlalchemy.MetaData` instance for getting physical
        table representations.
        
        Object attributes:
        
        * `fact_table` – the physical fact table - `sqlalchemy.Table` instance
        * `tables` – a dictionary where keys are table references (schema,
          table) or (shchema, alias) to real tables - `sqlalchemy.Table`
          instances
        
        """
        super(StarQueryBuilder, self).__init__()

        self.logger = cubes.common.get_logger()

        self.cube = cube
        self.mapper = mapper
        self.schema = mapper.schema
        self.metadata = metadata

        # Prepare physical fact table - fetch from metadata
        #
        self.fact_name = mapper.fact_name
        self.fact_table = sqlalchemy.Table(self.fact_name, self.metadata, 
                                           autoload=True, schema=self.schema)

        self.tables = {
                    (self.schema, self.fact_name): self.fact_table
                }

    def denormalized_statement(self, whereclause=None):
        """Return a SELECT statement for denormalized view. `whereclause` is
        same as SQLAlchemy `whereclause` for
        `sqlalchemy.sql.expression.select()`"""

        attributes = self.mapper.all_attributes()

        join_expression = self.join_expression_for_attributes(attributes)

        columns = [self.column(attr) for attr in attributes]

        select = sql.expression.select(columns, 
                                    whereclause=whereclause, 
                                    from_obj=join_expression,
                                    use_labels=True)

        return select
    
    def join_expression_for_attributes(self, attributes):
        """Returns a join expression for `attributes`"""
        physical_references = self.mapper.map_attributes(attributes)
        joins = self.mapper.relevant_joins(physical_references)
        return self.join_expression(joins)

    def join_expression(self, joins):
        """Create partial expression on a fact table with `joins` that can be
        used as core for a SELECT statement. `join` is a list of joins
        returned from mapper (most probably by `Mapper.relevant_joins()`)
        """
        
        self.logger.info("create basic expression with %d joins" % len(joins))

        expression = self.fact_table

        for join in joins:
            # self.logger.debug("join detail: %s" % (join.detail, ))

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

    def conditions_for_cell(self, cell):
        """Constructs conditions for all cuts in the `cell`. Returns a
        dictionary with keys:
        
        * ``conditions`` - SQL conditions
        * ``attributes`` - attributes that are involved in the conditions.
          This should be used for join construction.
        * ``group_by`` - attributes used for GROUP BY expression
        """
        
        attributes = set()
        conditions = []
        group_by = []

        for cut in cell.cuts:
            dim = self.cube.dimension(cut.dimension)

            if isinstance(cut, cubes.browser.PointCut):
                path = cut.path
                condition = self.condition_for_point(dim, path)

            elif isinstance(cut, cubes.browser.SetCut):
                conditions = []

                for path in cut.paths:
                    cond = self.condition_for_point(dim, path)
                    conditions.append(cond.condition)
                    attributes |= cond.attributes
                    group_by += cond.group_by

                condition = expression.or_(*conditions)

            elif isinstance(cut, cubes.browser.RangeCut):
                raise NotImplementedError("Condition for range cuts is not yet implemented")

            else:
                raise Exception("Only point and set cuts are supported in SQL browser at the moment")

            conditions.append(condition)
        
        condition = expression.and_(*conditions)

        return ConditionSet(attributes, condition, group_by)

    def condition_for_point(self, dim, path):
        """Returns a `ConditionSet` tuple (`attributes`, `conditions`,
        `group_by`) dimension `dim` point at `path`. It is a compound
        condition - one equality condition for each path element in form:
        ``level[i].key = path[i]``"""

        # TODO: add support for possible multiple hierarchies

        attributes = set()
        conditions = []
        group_by = []

        levels = dim.default_hierarchy.levels_for_path(path)

        if len(path) > len(levels):
            raise Exception("Path has more items (%d: %s) than there are levels (%d) "
                            "in dimension %s" % (len(path), path, len(levels), dim.name))

        level = None
        for level, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level.key)
            conditions.append(column == value)

            # FIXME: join attributes only if details are requested
            # Collect grouping columns
            for attr in level.attributes:
                column = self.column(attr)
                group_by.append(column)
                attributes.add(attr)

        condition = expression.and_(*conditions)
        
        return ConditionSet(attributes,condition,group_by)
        
        
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

    def column(self, attribute):
        """Return a column object for attribute"""

        ref = self.mapper.physical(attribute)
        table = self.table(ref.schema, ref.table)
        column = table.c[ref.column]
        return column.label(self.mapper.logical(attribute))
        
        return column
        
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
            browser = self.browser_for_cube(cube)
            issues += browser.validate()

        return issues
