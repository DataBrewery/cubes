# -*- coding=utf -*-
# Package imports
import json
import cubes
import logging
import ConfigParser

# Werkzeug - soft dependency
try:
    from werkzeug.routing import Map, Rule
    from werkzeug.wrappers import Request, Response
    from werkzeug.wsgi import ClosingIterator
    from werkzeug.exceptions import HTTPException, NotFound
    import werkzeug.serving
except:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Map = Rule = Request = ClosingIterator = HTTPException = _missing
    NotFound = Response = werkzeug = _missing

from cubes.workspace import create_slicer_context

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
                        endpoint = (controllers.ApplicationController, 'get_locales')),
    #
    # Model requests
    #
    Rule('/model',
                        endpoint = (controllers.ModelController, 'show')),

    Rule('/model/cubes',
                        endpoint = (controllers.ModelController, 'list_cubes')),
    Rule('/model/cube',
                        endpoint = (controllers.ModelController, 'get_default_cube')),
    Rule('/model/cube/<string:cube_name>',
                        endpoint = (controllers.ModelController, 'get_cube')),
    Rule('/model/cube/<string:cube_name>/dimensions',
                        endpoint = (controllers.ModelController, 'list_cube_dimensions')),

    Rule('/model/dimension/<string:dim_name>',
                        endpoint = (controllers.ModelController, 'dimension')),
    Rule('/model/dimension/<string:dim_name>/levels',
                        endpoint = (controllers.ModelController, 'dimension_levels')),
    Rule('/model/dimension/<string:dim_name>/level_names',
                        endpoint = (controllers.ModelController, 'dimension_level_names')),

    #
    # Aggregation browser requests
    #
    Rule('/cube/<string:cube>/aggregate',
                        endpoint = (controllers.CubesController, 'aggregate')),
    Rule('/cube/<string:cube>/facts',
                        endpoint = (controllers.CubesController, 'facts')),
    Rule('/cube/<string:cube>/fact/<string:fact_id>',
                        endpoint = (controllers.CubesController, 'fact')),
    Rule('/cube/<string:cube>/dimension/<string:dimension_name>',
                        endpoint = (controllers.CubesController, 'values')),
    Rule('/cube/<string:cube>/report', methods = ['POST'],
                        endpoint = (controllers.CubesController, 'report')),
    Rule('/cube/<string:cube>/cell',
                        endpoint = (controllers.CubesController, 'cell_details')),
    Rule('/cube/<string:cube>/details',
                        endpoint = (controllers.CubesController, 'details')),
    # Use default cube (specified in config as: [model] cube = ... )
    Rule('/aggregate',
                        endpoint = (controllers.CubesController, 'aggregate'),
                        defaults={"cube":None}),
    Rule('/facts',
                        endpoint = (controllers.CubesController, 'facts'),
                        defaults={"cube":None}),
    Rule('/fact/<string:fact_id>',
                        endpoint = (controllers.CubesController, 'fact'),
                        defaults={"cube":None}),
    Rule('/dimension/<string:dimension_name>',
                        endpoint=(controllers.CubesController, 'values'),
                        defaults={"cube":None}),
    Rule('/report', methods = ['POST'],
                        endpoint = (controllers.CubesController, 'report'),
                        defaults={"cube":None}),
    Rule('/cell',
                        endpoint = (controllers.CubesController, 'cell_details'),
                        defaults={"cube":None}),
    Rule('/details',
                        endpoint = (controllers.CubesController, 'details'),
                        defaults={"cube":None}),
    #
    # Other utility requests
    #
    Rule('/cube/<string:cube>/search',
                        endpoint = (controllers.SearchController, 'search')),

    Rule('/search',
                        endpoint = (controllers.SearchController, 'search'),
                        defaults={"cube":None})
])

class Slicer(object):

    def __init__(self, config=None):
        """Create a WSGI server for providing OLAP web service. You might
        provide ``config`` as ``ConfigParser`` object.
        """

        self.config = config
        self.initialize_logger()

        self.context = create_slicer_context(config)

        self.model = self.context["model"]
        self.locales = self.context["locales"]
        self.backend = self.context["backend"]

        ## Create workspace
        self.logger.info("using backend '%s'" % self.context["backend_name"])
        self.workspace = self.backend.create_workspace(self.model,
                                                       **self.context["workspace_options"])

    def initialize_logger(self):
        # Configure logger
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

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        urls = rules.bind_to_environ(environ)

        try:
            endpoint, params = urls.match()

            (ctrl_class, action) = endpoint
            response = self.dispatch(ctrl_class, action, request, params)
        except HTTPException, e:
            response = e

        return ClosingIterator(response(environ, start_response),
                               [local_manager.cleanup])

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def dispatch(self, ctrl_class, action_name, request, params):

        try:
            controller = ctrl_class(request.args,
                                    workspace=self.workspace,
                                    logger=self.logger,
                                    config=self.config)
            controller.request = request
            action = getattr(controller, action_name)
            response = action(**params)
            response.headers.add("Access-Control-Allow-Origin", "*")
        except cubes.CubesError as e:
            raise common.RequestError(str(e))

        return response


def create_server(config_file):
    """Returns a WSGI server application. `config_file` is a path to an `.ini`
    file with slicer server configuration."""

    try:
        config = ConfigParser.SafeConfigParser()
        config.read(config_file)
    except Exception as e:
        raise Exception("Unable to load configuration: %s" % e)

    return Slicer(config)

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
    werkzeug.serving.run_simple(host, port, application, use_reloader=use_reloader)

