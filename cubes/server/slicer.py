# Package imports
import json
import cubes
import logging

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
                        endpoint = (controllers.ApplicationController, 'locales')),
    Rule('/model',
                        endpoint = (controllers.ModelController, 'show')),
    Rule('/model/dimension/<string:dim_name>',
                        endpoint = (controllers.ModelController, 'dimension')),
    Rule('/model/cube',
                        endpoint = (controllers.ModelController, 'get_default_cube')),
    Rule('/model/cube/<string:cube_name>',
                        endpoint = (controllers.ModelController, 'get_cube')),
    Rule('/model/dimension/<string:dim_name>/levels',
                        endpoint = (controllers.ModelController, 'dimension_levels')),
    Rule('/model/dimension/<string:dim_name>/level_names',
                        endpoint = (controllers.ModelController, 'dimension_level_names')),
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
    Rule('/cube/<string:cube>/search',
                        endpoint = (controllers.SearchController, 'search')),

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
    Rule('/search',
                        endpoint = (controllers.SearchController, 'search'),
                        defaults={"cube":None})
])

class Slicer(object):

    def __init__(self, config=None):
        """Create a WSGI server for providing OLAP web service. You might provide ``config``
        as ``ConfigParser`` object.
        """

        self.config = config
        self.initialize_logger()

        self.context = create_slicer_context(config)

        self.model = self.context["model"]
        self.locales = self.context["locales"]
        self.backend = self.context["backend"]

        self.model_localizations = {}

        if self.locales is None:
            if self.model.locale:
                self.locales = [self.model.locale]
            else:
                self.locales = []

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

        controller = ctrl_class(request.args, self, self.config)
        controller.request = request
        action = getattr(controller, action_name)

        response = None
        try:
            response = action(**params)
            response.headers.add("Access-Control-Allow-Origin", "*")
        except cubes.CubesError as e:
            raise common.RequestError(str(e))

        return response

    def localized_model(self, locale=None):
        """Tries to translate the model. Looks for language in configuration file under 
        ``[translations]``, if no translation is provided, then model remains untouched."""

        # FIXME: Rewrite this to make it thread safer
        if not locale:
            return self.model
            
        self.logger.debug("localization to '%s' (current: '%s') requested (has: %s)" % (locale, self.model.locale, self.model_localizations.keys()))

        if locale in self.model_localizations:
            self.logger.debug("localization '%s' found" % locale)
            return self.model_localizations[locale]

        elif locale == self.model.locale:
            self.model_localizations[locale] = self.model
            return self.model

        elif self.config.has_option("translations", locale):
            path = self.config.get("translations", locale)
            self.logger.debug("translating model to '%s' translation path: %s" % (locale, path))
            with open(path) as handle:
                trans = json.load(handle)

            model = self.model.localize(trans)

            self.model_localizations[locale] = model
            return model

        else:
            raise common.RequestError("No translation for language '%s'" % locale)

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

