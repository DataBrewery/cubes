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
    from cubes.util import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Map = Rule = Request = ClosingIterator = HTTPException = _missing
    NotFound = Response = werkzeug = _missing

import common
# Local imports
import controllers
from utils import local_manager

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
    Rule('/cube/<string:cube>/search',
                        endpoint = (controllers.SearchController, 'search')),

    # FIXME: Remove this sooner or later:
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

        self.logger = logging.getLogger(cubes.common.logger_name)
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
    
        #
        # Load model
        #
        
        model_path = config.get("model", "path")
        try:
            self.model = cubes.load_model(model_path)
        except:
            if not model_path:
                model_path = 'unknown path'
            raise common.ServerError("Unable to load model from %s" % model_path)

        self.model_localizations = {}

        if config.has_option("model", "locales"):
            self.locales = config.get("model", "locales").split(",")
            self.logger.info("model locales: %s" % self.locales)
        elif self.model.locale:
            self.locales = [self.model.locale]
        else:
            self.locales = []
            
        if config.has_option("server","backend"):
            backend = config.get("server","backend")
        else:
            backend = "cubes.backends.sql.browser"
            
        self.create_workspace(backend, config)

    def create_workspace(self, backend_name, config):
        """Finds the backend object and creates a workspace.

        The backend should be a module with variables:
        
        * `config_section` - name of section where backend configuration is 
          found. This is optional and if does not exist or is ``None`` then
          ``[backend]`` section is used.
          
        The backend should provide a method `create_workspace(model, config)`
        which returns an initialized workspace object.

        The workspace object should implement `browser_for_cube(cube)`.
        """

        # FIXME: simplify this process

        path = backend_name.split(".")
        
        try:
            self.backend = globals()[path[0]]
            for current in path[1:]:
                self.backend = self.backend.__dict__[current]
        except KeyError:
            raise Exception("Unable to find backend module %s" % backend_name)

        self.logger.info("using backend '%s'" % backend_name)
            
        try:
            section = self.backend.config_section
        except:
            section = None
        
        section = section or "backend"
        
        if config.has_section(section):
            config_dict = dict(config.items(section))
        else:
            config_dict = {}
        
        self.workspace = self.backend.create_workspace(self.model, config_dict)
            
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

