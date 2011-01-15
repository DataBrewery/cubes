import os
import re
import logging

try:
    import json
except ImportError:
    import simplejson as json

def create_cube_view(cube, connection, name):
    """Create denormalized cube view in relational database in a DB2 API compatible connection
    
    Args:
        cube: cube object
        connection: DB2 API connection
        name: view name
    """
    
    builder = ViewBuilder(cube)
    builder.create_view(connection, name)

def create_materialized_cube_view(cube, connection, name):
    """Create denormalized cube view in relational database in a DB2 API compatible connection

    Args:
        cube: cube object
        connection: DB2 API connection
        name: materialized view (table) name
    """

    builder = ViewBuilder(cube)
    builder.create_materialized_view(connection, name)

class IgnoringDictionary(dict):
    """Simple dictionary extension that will ignore any keys of which values are empty (None/False)"""
    def setnoempty(self, key, value):
        """Set value in a dictionary if value is not null"""
        if value:
            self[key] = value

def default_logger_name():
    return 'brewery.cubes'
