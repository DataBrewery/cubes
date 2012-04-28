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
    from cubes.common import MissingPackage
    SphinxSearcher = MissingPackage("werkzeug", "Sphinx search ", 
                            source = "https://bitbucket.org/Stiivi/cubes-search")
    
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
        self.browser = self.app.workspace.browser_for_cube(self.cube, locale = self.locale)

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

        zipped = self.args.get("_zip")
        
        locale_tag = 0
        if self.locale:
            for (i, locale) in enumerate(self.app.locales):
                if locale == self.locale:
                    locale_tag = i
                    break
                    
        
        search_result = sphinx.search(query, dimension, locale_tag = locale_tag)
        
        # FIXME: remove "values" - backward compatibility key
        result = {
            "values": None,
            "matches": search_result.dimension_matches(dimension),
            "dimension": dimension,
            "total_found": search_result.total_found,
            "locale": self.locale,
            "_locale_tag": locale_tag,
            "_browser_locale": self.browser.locale
        }
        
        if search_result.error:
            result["error"] = search_result.error
        if search_result.warning:
            result["warning"] = search_result.warning

        return self.json_response(result)
