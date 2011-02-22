from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request
from werkzeug.wsgi import ClosingIterator
from werkzeug.exceptions import HTTPException

from utils import local, local_manager, url_map

import models
import controllers

url_map = Map([
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

    def __init__(self, model):
        local.application = self
        self.model = model

    def __call__(self, environ, start_response):
        local.application = self
        request = Request(environ)
        urls = url_map.bind_to_environ(environ)
        
        try:
            endpoint, params = urls.match()

            (controller_class, action) = endpoint
            controller = controller_class()
            
            response = self.dispatch(controller, action, request, params)
        except HTTPException, e:
            response = e
        return ClosingIterator(response(environ, start_response),
                               [local_manager.cleanup])
        
    def dispatch(self, controller, action_name, request, params):
        controller.request = request
        controller.params = params
        controller.model = self.model
        
        action = getattr(controller, action_name)

        return action()