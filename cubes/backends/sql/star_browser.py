# -*- coding=utf -*-
import cubes.browser
from cubes.backends.sql.common import AttributeMapper

# FIXME: required functionality
# 
# * number of items in drill-down
# * dimension values
# * drill-down sorting
# * drill-down pagination
# * drill-down limits (such as top-10)
# * facts sorting
# * facts pagination
# * dimension values sorting
# * dimension values pagination
# * remainder
# * ratio - aggregate sum(current)/sum(total) 
# * derived measures (should be in builder)

__all__ = ["StarBrowser"]

class StarBrowser(object):
    """docstring for StarBrowser"""
    
    def __init__(self, cube, locale = None):
        """StarBrowser is a SQL-based AggregationBrowser implementation that 
        can aggregate star and snowflake schemas without need of having 
        explicit view or physical denormalized table.

        Attributes:
        
        * `cube` - browsed cube

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
        self.mapper = AttributeMapper(cube, cube.mappings, locale)
        
    def aggregate(self, cell, measures = None, drilldown = None, details = False, **options):
        pass
