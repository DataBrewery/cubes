# Package imports
import json
import cubes
import logging

# Werkzeug - soft dependency
try:
    from werkzeug.routing import Map, Rule
    from werkzeug.wrappers import Request
    from werkzeug.wsgi import ClosingIterator
    from werkzeug.exceptions import HTTPException, NotFound
    from werkzeug.wrappers import Response
    import werkzeug.serving
except:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Map = Rule = Request = ClosingIterator = HTTPException = _missing
    NotFound = Response = werkzeug = _missing

from cubes.util import create_slicer_context

import common
# Local imports
import controllers
from utils import local_manager

# TODO: this deserves Flask!

rules = Map([
    Rule('/', endpoint = (controllers.ApplicationController, 'index')),
    Rule('/version', 
                        endpoint = (controllers.ApplicationController, 'version')),
    Rule('/locales', 
                        endpoint = (controllers.ApplicationController, 'locales')),
    Rule('/model', 
                        endpoint = (controllers.ModelController, 'show')),
    Rule('/model/dimension/<string:name>',
                        endpoint = (controllers.ModelController, 'dimension')),
    Rule('/model/cube',
                        endpoint = (controllers.ModelController, 'get_default_cube')),
    Rule('/model/cube/<string:name>',
                        endpoint = (controllers.ModelController, 'get_cube')),
    Rule('/model/dimension/<string:name>/levels', 
                        endpoint = (controllers.ModelController, 'dimension_levels')),
    Rule('/model/dimension/<string:name>/level_names', 
                        endpoint = (controllers.ModelController, 'dimension_level_names')),
    Rule('/cube/<string:cube>/aggregate', 
                        endpoint = (controllers.CubesController, 'aggregate')),
    Rule('/cube/<string:cube>/facts', 
                        endpoint = (controllers.CubesController, 'facts')),
    Rule('/cube/<string:cube>/fact/<string:id>', 
                        endpoint = (controllers.CubesController, 'fact')),
    Rule('/cube/<string:cube>/dimension/<string:dimension>', 
                        endpoint = (controllers.CubesController, 'values')),
    Rule('/cube/<string:cube>/report', methods = ['POST'],
                        endpoint = (controllers.CubesController, 'report')),
    Rule('/cube/<string:cube>/details',
                        endpoint = (controllers.CubesController, 'details')),
    Rule('/cube/<string:cube>/search',
                        endpoint = (controllers.SearchController, 'search')),

    # Use default cube (specified in config as: [model] cube = ... )
    Rule('/aggregate', 
                        endpoint = (controllers.CubesController, 'aggregate')),
    Rule('/facts', 
                        endpoint = (controllers.CubesController, 'facts')),
    Rule('/fact/<string:id>', 
                        endpoint = (controllers.CubesController, 'fact')),
    Rule('/dimension/<string:dimension>', 
                        endpoint = (controllers.CubesController, 'values')),
    Rule('/report', methods = ['POST'],
                        endpoint = (controllers.CubesController, 'report')),
    Rule('/details', 
                        endpoint = (controllers.CubesController, 'details')),
    Rule('/search',
                        endpoint = (controllers.SearchController, 'search'))
])

class Slicer(object):

    def __init__(self, config = None):
        """Create a WSGI server for providing OLAP web service. You might provide ``config``
        as ``ConfigParser`` object.
        """
        
        self.config = config

        #
        # Configure logger
        #

        self.logger = cubes.common.get_logger()
        if self.config.has_option("server", "log"):
            formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s')
            handler = logging.FileHandler(self.config.get("server", "log"))
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        if self.config.has_option("server", "log_level"):
            level_str = self.config.get("server", "log_level").lower()
            levels = {  "info": logging.INFO, 
                        "debug": logging.DEBUG, 
                        "warn":logging.WARN,
                        "error": logging.ERROR}
            if level_str not in levels:
                self.logger.warn("Unknown logging level '%s', keeping default" % level_str)
            else:
                self.logger.setLevel(levels[level_str])

        self.logger.debug("loading model")
    
        context = create_slicer_context(config)
        self.model = context["model"]
        self.locales = context["locales"]
        self.backend = context["backend"]
        
        self.model_localizations = {}

        if self.locales is None:
            if self.model.locale:
                self.locales = [self.model.locale]
            else:
                self.locales = []
            
        ##
        # Create workspace
        ##
                    
        self.logger.info("using backend '%s'" % context["backend_name"])
            
        self.workspace = self.backend.create_workspace(self.model,
                                                       **context["workspace_options"])
            
    def __call__(self, environ, start_response):
        request = Request(environ)
        urls = rules.bind_to_environ(environ)
        
        try:
            endpoint, params = urls.match()

            (controller_class, action) = endpoint
            controller = controller_class(self, self.config)

            response = self.dispatch(controller, action, request, params)
        except HTTPException, e:
            response = e

        return ClosingIterator(response(environ, start_response),
                               [local_manager.cleanup])
        
    def dispatch(self, controller, action_name, request, params):

        controller.request = request
        controller.args = request.args
        controller.params = params

        action = getattr(controller, action_name)

        controller.initialize()

        response = None
        try:
            response = action()
            response.headers.add("Access-Control-Allow-Origin", "*")
        finally:
            controller.finalize()

        return response

    def error(self, message, exception):
        string = json.dumps({"error": {"message": message, "reason": str(exception)}})
        return Response(string, mimetype='application/json')
        
def run_server(config):
    """Run OLAP server with configuration specified in `config`"""
    if config.has_option("server", "host"):
        host = config.get("server", "host")
    else: 
        host = "localhost"

    if config.has_option("server", "port"):
        port = config.getint("server", "port")
    else:
        port = 5000

    if config.has_option("server", "reload"):
        use_reloader = config.getboolean("server", "reload")
    else:
        use_reloader = False

    application = Slicer(config)
    werkzeug.serving.run_simple(host, port, application, use_reloader = use_reloader)

