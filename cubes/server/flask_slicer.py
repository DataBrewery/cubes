# -*- coding=utf -*-
from flask import Blueprint, Flask, Response, request, g, current_app
from werkzeug.local import LocalProxy

import ConfigParser
from ..workspace import Workspace
from ..errors import *
from .common import *
from .errors import *

from cubes import __version__

# TODO: this belongs to the calendar
from .utils import set_default_tz
import pytz

__all__ = (
    "slicer",
    "create_server",
    "run_server",
    "API_VERSION"
)


API_VERSION = 2


slicer = Blueprint('slicer', __name__)


# Application Context
# ===================
#
# Readability proxies

def _get_workspace():
    return current_app.workspace
def _get_logger():
    return current_app.cubes_logger

workspace = LocalProxy(_get_workspace)
logger = LocalProxy(_get_logger)

def _read_config(config):
    if isinstance(config, basestring):
        try:
            path = config
            config = ConfigParser.SafeConfigParser()
            config.read(path)
        except Exception as e:
            raise Exception("Unable to load configuration: %s" % e)
    return config


def create_server(config):
    """Returns a Flask server application. `config` is a path to a
    ``slicer.ini`` file with Cubes workspace and server configuration."""

    config = _read_config(config)
    app = Flask("slicer")
    app.register_blueprint(slicer, config=config)

    app.config["CUBES_CONFIG"] = config

    return app


def run_server(config, debug=False):
    """Run OLAP server with configuration specified in `config`"""

    config = _read_config(config)
    app = create_server(config)

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

    if config.has_option('server', 'processes'):
        processes = config.getint('server', 'processes')
    else:
        processes = 1

    # TODO :replace this with [workspace]timezone in future calendar module
    if config.has_option('server', 'tz'):
        set_default_tz(pytz.timezone(config.get("server", "tz")))

    app.run(host, port, debug=debug, processes=processes,
            use_reloader=use_reloader)

# Before
# ------
@slicer.record_once
def initialize_slicer(state):
    """Create the workspace and configure the application context from the
    ``slicer.ini`` configuration."""

    with state.app.app_context():
        config = state.options["config"]

        # Create workspace
        current_app.workspace = Workspace(state.options["config"])
        current_app.cubes_logger = current_app.workspace.logger
        current_app.slicer = _Configuration()

        # Configure the application
        _configure_option(config, "prettyprint", False, "bool")
        _configure_option(config, "json_record_limit", 1000, "int")
        _configure_option(config, "authorization_method", "http_basic",
                          allowed=["http_basic"])


class _Configuration(dict):
    def __getattr__(self, attr):
        try:
            return super(_Configuration, self).__getitem__(attr)
        except KeyError:
            return super(_Configuration, self).__getattribute__(attr)

    def __setattr__(self, attr, value):
        self.__setitem__(attr,value)


def _configure_option(config, option, default, type_=None, allowed=None):
    """Copies the `option` into the application config dictionary. `default`
    is a default value, if there is no such option in `config`. `type_` can be
    `bool`, `int` or `string` (default). If `allowed` is specified, then the
    option should be only from the list of allowed options, otherwise a
    `ConfigurationError` exception is raised.
    """

    if config.has_option("server", option):
        if type_ == "bool":
            value = config.getboolean("server", option)
        elif type_ == "int":
            value = config.getint("server", option)
        else:
            value = config.get("server", option)
    else:
        value = default

    if allowed and value not in allowed:
        raise ConfigurationError("Invalued value '%s' for option '%s'"
                                 % (value, option))

    setattr(current_app.slicer, option, value)

@slicer.before_request
def before_request():
    # TODO: setup language

    # Copy from the application context
    g.json_record_limit = current_app.slicer.json_record_limit

    if "prettyprint" in request.args:
        g.prettyprint = str_to_bool(request.args.get("prettyprint"))
    else:
        g.prettyprint = current_app.slicer.prettyprint

    if "page" in request.args:
        try:
            g.page = int(request.args.get("page"))
        except ValueError:
            raise RequestError("'page' should be a number")

    if "pagesize" in request.args:
        try:
            g.pagesize = int(request.args.get("pagesize"))
        except ValueError:
            raise RequestError("'pagesize' should be a number")

    # Collect orderings:
    # order is specified as order=<field>[:<direction>]
    # examples:
    #
    #     order=date.year     # order by year, unspecified direction
    #     order=date.year:asc # order by year ascending
    #
    g.order = []
    for orders in request.args.getlist("order"):
        for order in orders.split(","):
            split = order.split(":")
            if len(split) == 1:
                g.order.append( (order, None) )
            else:
                g.order.append( (split[0], split[1]) )

@slicer.before_request
def prepare_authorization():
    if current_app.slicer.authorization_method == "http_basic":
    # Method: http_basic
        auth_header = request.headers.get('authorization')
        if auth_header:
            authorization = parse_authorization_header(auth_header)
            g.auth_token = authorization.username
        else:
            g.auth_token = None
    else:
        raise InternalError("Unsupported authorization method: %s"
                            % current_app.slicer.auth_method)




# Utils
# =====


def jsonify(obj):
    """Returns a ``application/json`` `Response` object with `obj` converted
    to JSON."""

    if g.prettyprint:
        indent = 4
    else:
        indent = None

    encoder = SlicerJSONEncoder(indent=indent)
    encoder.iterator_limit = g.json_record_limit
    data = encoder.iterencode(obj)

    return Response(data, mimetype='application/json')


# Endpoints
# =========

@slicer.route("/")
def show_index():
    return "Cubes"


@slicer.route("/version")
def show_version():
    info = {
        "version": __version__,
        # Backward compatibility key
        "server_version": __version__,
        "api_version": API_VERSION
    }
    return jsonify(info)


@slicer.route("/info")
def show_info():
    info = {
        "authorization_method": current_app.slicer.authorization_method,
        "version": __version__
    }
    return jsonify(info)

@slicer.route("/cubes")
def list_cubes():
    pass


@slicer.route("/cube/<cube>/model")
def cube_model(cube):
    pass


@slicer.route("/cube/<cube>/aggregate")
def cube_aggregate(cube):
    pass


@slicer.route("/cube/<cube>/facts")
def cube_facts(cube):
    pass


@slicer.route("/cube/<cube>/fact/<fact_id>")
def cube_fact(cube, fact_id):
    pass


@slicer.route("/cube/<cube>/members")
def cube_members(cube):
    pass


@slicer.route("/cube/<cube>/cell")
def cube_cell(cube):
    pass


@slicer.route("/cube/<cube>/report")
def cube_report(cube):
    pass


@slicer.route("/cube/<cube>/search")
def cube_search(cube):
    pass
