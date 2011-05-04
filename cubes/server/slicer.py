# Werkzeug
from werkzeug.routing import Map, Rule
from werkzeug.wrappers import Request
from werkzeug.wsgi import ClosingIterator
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.wrappers import Response
import werkzeug.serving

# Package imports
import json
import sqlalchemy
import cubes
import logging
import common

# Local imports
from utils import local, local_manager, url_map
import controllers

rules = Map([
    Rule('/', endpoint = (controllers.ApplicationController, 'index')),
    Rule('/version', 
                        endpoint = (controllers.ApplicationController, 'version')),
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

        # Configure logger

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

        db_defaults = {
            "schema": None,
            "view_prefix": None,
            "view_suffix": None
        }

        self.dburl = config.get("db", "url")

        self.schema = None
        if config.has_option("db","schema"):
            self.schema = config.get("db","schema")

        self.view_prefix = None
        if config.has_option("db","view_prefix"):
            self.view_prefix = config.get("db", "view_prefix")

        self.view_suffix = None
        if config.has_option("db","view_suffix"):
            self.view_suffix = config.get("db", "view_suffix")

        self.engine = sqlalchemy.create_engine(self.dburl)
        
        self.logger.info("creatign new database engine")

        model_path = config.get("model", "path")
        try:
            self.model = cubes.load_model(model_path)
        except:
            if not model_path:
                model_path = 'unknown path'
            raise common.ServerError("Unable to load model from %s" % model_path)

        if config.has_option("model", "locales"):
            self.locales = config.get("model", "locales").split(",")
            self.logger.info("model locales: %s" % self.locales)
        elif self.model.locale:
            self.locales = [self.model.locale]
        else:
            self.locales = []
            
        self.workspace = cubes.backends.sql.SQLWorkspace(self.model, self.engine, self.schema, 
                                        name_prefix = self.view_prefix,
                                        name_suffix = self.view_suffix)
        
    def __call__(self, environ, start_response):
        local.application = self
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
        try:
            retval = action()
        finally:
            controller.finalize()

        return retval

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

