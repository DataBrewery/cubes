# -*- coding=utf -*-
import cubes.browser
from cubes.backends.sql.common import AttributeMapper, JoinFinder

# Required functionality checklist
# 
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
    
    def __init__(self, cube, locale=None, dimension_prefix=None, schema=None):
        """StarBrowser is a SQL-based AggregationBrowser implementation that 
        can aggregate star and snowflake schemas without need of having 
        explicit view or physical denormalized table.

        Attributes:
        
        * `cube` - browsed cube
        * `dimension_prefix` - prefix for dimension tables
        * `schema` - default database schema name

        .. warning:
            
            Not fully implemented yet.

        **Limitations:**
        
        * only one locale can be used for browsing at a time
        * locale is implemented as denormalized: one column for each language

        """
        super(StarBrowser, self).__init__()

        if cube == None:
            raise Exception("Cube for browser should not be None.")
            
        self.cube = cube
        self.dimension_prefix = dimension_prefix
        self.schema = schema

        self.mappings = cube.mappings
        
        self.locale = locale
        self.mapper = AttributeMapper(cube, self.mappings, self.locale)
        self.mapper.dimension_table_prefix = dimension_prefix
        self.joinfinder = JoinFinder(cube, joins=cube.joins, mapper=self.mapper)
    
    def fact(self, key):
        """Get the fact from cube."""

        attributes = []

        # 1. get all fact attributes: key, measures, details
        attributes += self.cube.measures
        attributes += self.cube.details

        for dim in self.cube.dimensions:
            attributes += dim.all_attributes()

        # 2. Get physical references (schema, table, column)
        physical = []
        for attr in attributes:
            ref = self.mapper.physical(attr.dimension, attr)
            physical.append(ref)
            print list(ref)

        # 3. Collect tables
        # tables = {(ref[0], ref[1]) for ref in physical}
        # print tables

        joins = self.joinfinder.relevant_joins(physical)
        print joins
        
        #     
        # 
        # condition = self.key_column == fact_id
        # columns = [col.column for col in self.selection.values()]
        # 
        # stmt = expression.select(columns, 
        #                             whereclause = condition, 
        #                             from_obj = self.view)
        # return stmt
        
        return {}
    
    def aggregate(self, cell, measures = None, drilldown = None, details = False, **options):
        pass
