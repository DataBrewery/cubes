# -*- coding=utf -*-
# Package imports
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
except ImportError:
    from ..common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Map = Rule = Request = ClosingIterator = HTTPException = _missing
    NotFound = Response = werkzeug = _missing
try:
    import pytz
except ImportError:
    from ..common import MissingPackage
    _missing = MissingPackage("pytz", "Time zone support in the server")

from ..workspace import Workspace
from ..common import *

from .common import *
from .errors import *
from .controllers import *
from .utils import local_manager, set_default_tz

# TODO: this deserves Flask!

rules = Map([
    Rule('/', endpoint=(ApplicationController, 'index')),
    Rule('/version',
                        endpoint=(ApplicationController, 'version')),
    Rule('/locales',
                        endpoint=(ApplicationController, 'get_locales')),
    #
    # Model requests
    #
    Rule('/model',
                        endpoint=(ModelController, 'show')),

    Rule('/cubes',
                        endpoint=(ModelController, 'list_cubes')),
    Rule('/model/cubes',
                        endpoint=(ModelController, 'list_cubes')),
    Rule('/model/cube',
                        endpoint=(ModelController, 'get_default_cube')),
    Rule('/model/cube/<string:cube_name>',
                        endpoint=(ModelController, 'get_cube')),

    Rule('/model/dimension/<string:dim_name>',
                        endpoint=(ModelController, 'dimension')),

    #
    # Aggregation browser requests
    #
    Rule('/cube/<string:cube_name>/model',
                        endpoint=(ModelController, 'get_cube')),
    Rule('/cube/<string:cube>/aggregate',
                        endpoint=(CubesController, 'aggregate')),
    Rule('/cube/<string:cube>/facts',
                        endpoint=(CubesController, 'facts')),
    Rule('/cube/<string:cube>/fact/<string:fact_id>',
                        endpoint=(CubesController, 'fact')),
    Rule('/cube/<string:cube>/dimension/<string:dimension_name>',
                        endpoint=(CubesController, 'values')),
    Rule('/cube/<string:cube>/report', methods = ['POST'],
                        endpoint=(CubesController, 'report')),
    Rule('/cube/<string:cube>/cell',
                        endpoint=(CubesController, 'cell_details')),
    Rule('/cube/<string:cube>/details',
                        endpoint=(CubesController, 'details')),
    Rule('/cube/<string:cube>/build',
                        endpoint=(CubesController, 'build')),
    # Use default cube (specified in config as: [model] cube = ... )
    Rule('/aggregate',
                        endpoint=(CubesController, 'aggregate'),
                        defaults={"cube":None}),
    Rule('/facts',
                        endpoint=(CubesController, 'facts'),
                        defaults={"cube":None}),
    Rule('/fact/<string:fact_id>',
                        endpoint=(CubesController, 'fact'),
                        defaults={"cube":None}),
    Rule('/dimension/<string:dimension_name>',
                        endpoint=(CubesController, 'values'),
                        defaults={"cube":None}),
    Rule('/report', methods = ['POST'],
                        endpoint=(CubesController, 'report'),
                        defaults={"cube":None}),
    Rule('/cell',
                        endpoint=(CubesController, 'cell_details'),
                        defaults={"cube":None}),
    Rule('/details',
                        endpoint=(CubesController, 'details'),
                        defaults={"cube":None}),
    #
    # Other utility requests
    #
    Rule('/cube/<string:cube>/search',
                        endpoint = (SearchController, 'search')),

    Rule('/search',
                        endpoint = (SearchController, 'search'),
                        defaults={"cube":None}),
])


class Slicer(object):

    def __init__(self, config=None):
        """Create a WSGI server for providing OLAP web service. You might
        provide ``config`` as ``ConfigParser`` object.
        """

        self.config = config
        self.initialize_logger()

        self.workspace = Workspace(config=config)
        self.locales = self.workspace.locales

    def initialize_logger(self):
        # Configure logger
        self.logger = get_logger()

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

        if self.config.has_option("server", "debug_exceptions"):
            self.debug_exceptions = True
        else:
            self.debug_exceptions = False

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

        controller = ctrl_class(request.args,
                                workspace=self.workspace,
                                logger=self.logger,
                                config=self.config)
        controller.request = request
        action = getattr(controller, action_name)

        try:
            response = action(**params)
        except cubes.UserError as e:
            if self.debug_exceptions:
                raise
            else:
                raise RequestError(str(e))
        else:
            response.headers.add("Access-Control-Allow-Origin", "*")

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

    if config.has_option('server', 'tz'):
        set_default_tz(pytz.timezone(config.get("server", "tz")))

    if config.has_option("server", "port"):
        port = config.getint("server", "port")
    else:
        port = 5000

    if config.has_option("server", "reload"):
        use_reloader = config.getboolean("server", "reload")
    else:
        use_reloader = False

    if config.has_option('server', 'processes'):
        processes = config.getint('server', 'processes')
    else:
        processes = 1

    application = Slicer(config)
    werkzeug.serving.run_simple(host, port, application,
                                processes=processes,
                                use_reloader=use_reloader)

