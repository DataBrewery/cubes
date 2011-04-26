"""Experimental search module for Slicer Server.

WARNING: This is just preliminary prototype, use at your own risk of having your application broken
later.

Requires sphinx_search package from:

    https://bitbucket.org/Stiivi/cubes-search

"""
import application_controller
from .. import common

try:
    from cubes_search.sphinx import SphinxSearcher
except:
    SphinxSearcher = None
    
class SearchController(application_controller.ApplicationController):
    """docstring for SearchController
    
    Config options:
    
    sql_index_table: table name
    sql_schema
    sql_url
    search_backend: sphinx otherwise we raise exception.
    
    """        

    def initialize(self):
        # FIXME: remove this (?)
        cube_name = self.params.get("cube")
        if not cube_name:
            cube_name = self.config.get("model", "cube")

        self.cube = self.model.cube(cube_name)
        self.browser = self.app.workspace.browser_for_cube(self.cube)

        if self.config.has_option("sphinx", "host"):
            self.sphinx_host = self.config.get("sphinx","host")
        else:
            self.sphinx_host = None
            
        if self.config.has_option("sphinx", "port"):
            self.sphinx_port = self.config.getint("sphinx","port")
        else:
            self.sphinx_port = None
        
    def search(self):
        
        if not SphinxSearcher:
            raise common.ServerError("Search extension cubes_search is not installed")

        sphinx = SphinxSearcher(self.browser, self.sphinx_host, self.sphinx_port)
        
        dimension = self.args.get("dimension")
        if not dimension:
            return self.error("No dimension provided")

        query = self.args.get("q")
        if not query:
            query = self.args.get("query")
        
        if not query:
            return self.error("No query provided")
        
        result = {
            "values": search_result.values(dimension),
            "dimension": dimension,
            "total_found": search_result.total_found
        }
        
        return self.json_response(result)
