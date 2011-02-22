from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request
from werkzeug.wsgi import ClosingIterator
from werkzeug.exceptions import HTTPException

from utils import local, local_manager, url_map

import models
import controllers

rules = Map([
    Rule('/', endpoint = (controllers.ApplicationController, 'index')),
    Rule('/model', 
                        endpoint = (controllers.ModelController, 'show')),
    Rule('/model/dimension/<string:name>',
                        endpoint = (controllers.ModelController, 'dimension')),
    Rule('/model/dimension/<string:name>/levels', 
                        endpoint = (controllers.ModelController, 'dimension_levels')),
    Rule('/model/dimension/<string:name>/level_names', 
                        endpoint = (controllers.ModelController, 'dimension_level_names')),
    Rule('/aggregate', 
                        endpoint = (controllers.AggregationController, 'aggregate')),
    Rule('/dimension/<string:name>', 
                        endpoint = (controllers.AggregationController, 'dimension_values')),
    Rule('/facts', 
                        endpoint = (controllers.AggregationController, 'facts')),
    Rule('/fact/<string:id>', 
                        endpoint = (controllers.AggregationController, 'fact')),
    Rule('/report/<string:id>', 
                        endpoint = (controllers.AggregationController, 'report'))
])

class Slicer(object):

    def __init__(self, config = None):
        """Create a WSGI server for providing OLAP web service.
        
        API:
            * ``/model`` - get model metadata
            * ``/model/dimension/dimension_name`` - get dimension metadata
            * ``/model/dimension/dimension_name/levels`` - get levels of default dimension hierarchy
            * ``/model/dimension/dimension_name/level_names`` - get just names of levels 
            * ``/aggregate`` - return aggregation result
        
        
        """
        
        local.application = self
        self.config = config

    def __call__(self, environ, start_response):
        local.application = self
        request = Request(environ)
        urls = rules.bind_to_environ(environ)
        
        try:
            endpoint, params = urls.match()
            print "ENDPOINT: %s PARAMS: %s" % (endpoint, params)
            (controller_class, action) = endpoint
            controller = controller_class(self.config)
            
            response = self.dispatch(controller, action, request, params)
        except HTTPException, e:
            response = e
        return ClosingIterator(response(environ, start_response),
                               [local_manager.cleanup])
        
    def dispatch(self, controller, action_name, request, params):
        controller.initialize()

        controller.request = request
        controller.params = params
        
        action = getattr(controller, action_name)
        retval = action()
        controller.finalize()

        return retval
