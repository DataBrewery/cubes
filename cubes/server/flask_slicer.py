# -*- coding=utf -*-
from flask import Blueprint, Flask, Response, request, g, current_app
from werkzeug.local import LocalProxy
from functools import wraps

import ConfigParser
from ..workspace import Workspace
from ..auth import NotAuthorized
from ..browser import Cell, cuts_from_string, SPLIT_DIMENSION_NAME
from ..errors import *
from .common import *
from .errors import *

from cubes import __version__

# TODO: this belongs to the calendar
from .utils import set_default_tz
import pytz

try:
    import cubes_search
except ImportError:
    cubes_search = None


__all__ = (
    "slicer",
    "create_server",
    "run_server",
    "API_VERSION"
)


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

# Utils
# -----


def prepare_cell(argname="cut", target="cell"):
    """Sets `g.cell` with a `Cell` object from argument with name `argname`"""
    # Used by prepare_browser_request and in /aggregate for the split cell

    cuts = []
    for cut_string in request.args.getlist(argname):
        cuts += cuts_from_string(cut_string)

    if cuts:
        cell = Cell(g.cube, cuts)
    else:
        cell = None

    setattr(g, target, cell)

# Before
# ------
@slicer.record_once
def initialize_slicer(state):
    """Create the workspace and configure the application context from the
    ``slicer.ini`` configuration."""

    with state.app.app_context():
        config = state.options["config"]

        # Create workspace
        current_app.slicer = _Configuration()
        current_app.slicer.config = config
        current_app.workspace = Workspace(state.options["config"])
        current_app.cubes_logger = current_app.workspace.logger

        # Configure the application
        _configure_option(config, "prettyprint", False, "bool")
        _configure_option(config, "json_record_limit", 1000, "int")
        _configure_option(config, "authorization_method", "http_basic",
                          allowed=["http_basic"])


@slicer.before_request
def prepare_browser_request():
    """Prepares three global variables: `g.cube`, `g.browser` and `g.cell`."""
    cube_name = request.view_args.get("cube_name")
    if cube_name:
        cube = workspace.cube(cube_name)
    else:
        cube = None

    g.cube = cube
    g.browser = workspace.browser(g.cube)
    prepare_cell()

    if "page" in request.args:
        try:
            g.page = int(request.args.get("page"))
        except ValueError:
            raise RequestError("'page' should be a number")
    else:
        g.page = None

    if "pagesize" in request.args:
        try:
            g.page_size = int(request.args.get("pagesize"))
        except ValueError:
            raise RequestError("'pagesize' should be a number")
    else:
        g.page_size = None

    # Collect orderings:
    # order is specified as order=<field>[:<direction>]
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
def before_request():
    # TODO: setup language

    # Copy from the application context
    g.json_record_limit = current_app.slicer.json_record_limit

    if "prettyprint" in request.args:
        g.prettyprint = str_to_bool(request.args.get("prettyprint"))
    else:
        g.prettyprint = current_app.slicer.prettyprint



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

# Authorization
# =============

@slicer.before_request
def prepare_authorization():
    g.authorization_token = None

    if current_app.slicer.authorization_method == "http_basic":
    # Method: http_basic

        if request.authorization:
            g.authorization_token = request.authorization.username
    else:
        raise InternalError("Unsupported authorization method: %s"
                            % current_app.slicer.auth_method)


def authorize_cube(cube):
    if not workspace.authorizer:
        return

    try:
        workspace.authorizer.authorize(g.authorization_token, cube)
    except NotAuthorized as e:
        raise NotAuthorizedError(exception=e)

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
    if "cached_cube_list" in current_app.slicer:
        cube_list = current_app.slicer.cached_cube_list
    else:
        cube_list = workspace.list_cubes()
        current_app.slicer.cached_cube_list = cube_list

    return jsonify(cube_list)


@slicer.route("/cube/<cube_name>/model")
def cube_model(cube_name):
    cube = workspace.cube(cube_name)
    authorize_cube(cube)

    # TODO: only one option: private or public
    response = cube.to_dict(expand_dimensions=True,
                            with_mappings=False,
                            full_attribute_names=True,
                            create_label=True)

    response["features"] = workspace.cube_features(cube)

    return jsonify(response)


@slicer.route("/cube/<cube_name>/aggregate")
def aggregate(cube_name):
    cube = g.cube

    output_format = validated_parameter(request.args, "format",
                                        values=["json", "csv"],
                                        default="json")

    header_type = validated_parameter(request.args, "header",
                                      values=["names", "labels", "none"],
                                      default="labels")

    fields_str = request.args.get("fields")
    if fields_str:
        fields = fields_str.lower().split(',')
    else:
        fields = None

    # Aggregates
    # ----------

    aggregates = []
    for agg in request.args.getlist("aggregates") or []:
        aggregates += agg.split("|")

    drilldown = []

    ddlist = request.args.getlist("drilldown")
    if ddlist:
        for ddstring in ddlist:
            drilldown += ddstring.split("|")

    prepare_cell("split", "split")

    result = g.browser.aggregate(g.cell,
                                 aggregates=aggregates,
                                 drilldown=drilldown,
                                 split=g.split,
                                 page=g.page,
                                 page_size=g.page_size,
                                 order=g.order)

    if output_format == "json":
        return jsonify(result)
    elif output_format != "csv":
        raise RequestError("unknown response format '%s'" % output_format)

    # csv
    if header_type == "names":
        header = result.labels
    elif header_type == "labels":
        header = []
        for l in result.labels:
            # TODO: add a little bit of polish to this
            if l == SPLIT_DIMENSION_NAME:
                header.append('Matches Filters')
            else:
                header += [ attr.label or attr.name for attr in cube.get_attributes([l], aggregated=True) ]
    else:
        header = None

    fields = result.labels
    generator = CSVGenerator(result,
                             fields,
                             include_header=bool(header),
                             header=header)

    return Response(generator.csvrows(),
                    mimetype='text/csv')


@slicer.route("/cube/<cube_name>/facts")
def cube_facts(cube_name):
    # Request parameters
    output_format = validated_parameter(request.args, "format",
                                        values=["json", "csv"],
                                        default="json")

    header_type = validated_parameter(request.args, "header",
                                      values=["names", "labels", "none"],
                                      default="labels")

    fields_str = request.args.get("fields")
    if fields_str:
        fields = fields_str.lower().split(',')
    else:
        fields = None

    # fields contain attribute names
    if fields:
        attributes = g.cube.get_attributes(fields)
    else:
        attributes = g.cube.all_attributes

    # Construct the field list
    fields = [attr.ref() for attr in attributes]

    # Get the result
    result = g.browser.facts(g.cell,
                             fields=fields,
                             order=g.order,
                             page=g.page,
                             page_size=g.page_size)

    # Add cube key to the fields (it is returned in the result)
    fields.insert(0, g.cube.key)

    # Construct the header
    if header_type == "names":
        header = fields
    elif header_type == "labels":
        header = [attr.label or attr.name for attr in attributes]
        header.insert(0, g.cube.key or "id")
    else:
        header = None

    # Get the facts iterator. `result` is expected to be an iterable Facts
    # object
    facts = iter(result)

    if output_format == "json":
        return jsonify(facts)
    elif output_format == "csv":
        if not fields:
            fields = result.labels

        generator = CSVGenerator(facts,
                                 fields,
                                 include_header=bool(header),
                                 header=header)

        return Response(generator.csvrows(),
                        mimetype='text/csv')


@slicer.route("/cube/<cube_name>/fact/<fact_id>")
def cube_fact(cube_name, fact_id):
    fact = g.browser.fact(fact_id)

    if fact:
        return jsonify(fact)
    else:
        raise NotFoundError(fact_id, "fact",
                            message="No fact with id '%s'" % fact_id)


@slicer.route("/cube/<cube_name>/members/<dimension_name>")
def cube_members(cube_name, dimension_name):
    depth = request.args.get("depth")

    if depth:
        try:
            depth = int(depth)
        except ValueError:
            raise RequestError("depth should be an integer")

    try:
        dimension = g.cube.dimension(dimension_name)
    except KeyError:
        raise NotFoundError(dim_name, "dimension",
                            message="Dimension '%s' was not found" % dim_name)

    hier_name = request.args.get("hierarchy")
    hierarchy = dimension.hierarchy(hier_name)

    values = g.browser.members(g.cell,
                               dimension,
                               depth=depth,
                               hierarchy=hierarchy,
                               page=g.page,
                               page_size=g.page_size)

    depth = depth or len(hierarchy)

    result = {
        "dimension": dimension.name,
        "hierarchy": hierarchy.name,
        "depth": len(hierarchy) if depth is None else depth,
        "data": values
    }

    return jsonify(result)


@slicer.route("/cube/<cube_name>/cell")
def cube_cell(cube_name):
    details = g.browser.cell_details(g.cell)
    cell_dict = g.cell.to_dict()

    for cut, detail in zip(cell_dict["cuts"], details):
        cut["details"] = detail

    return jsonify(cell_dict)


@slicer.route("/cube/<cube>/report")
def cube_report(cube):
    report_request = self.json_request()

    try:
        queries = report_request["queries"]
    except KeyError:
        raise RequestError("Report request does not contain 'queries' key")

    cell_cuts = report_request.get("cell")

    if cell_cuts:
        # Override URL cut with the one in report
        cuts = [cut_from_dict(cut) for cut in cell_cuts]
        cell = Cell(g.cube, cuts)
        logger.info("using cell from report specification (URL parameters "
                    "are ignored)")
    else:
        cell = g.cell

    result = g.browser.report(cell, queries)

    return jsonify(result)


@slicer.route("/cube/<cube>/search")
def cube_search(cube):
    # TODO: this is ported from old Werkzeug slicer, requires revision

    config = current_app.config
    if config.has_section("search"):
        options = dict(config.items("search"))
        engine_name = options.pop("engine")
    else:
        raise ConfigurationError("Search engine is not configured.")

    logger.debug("using search engine: %s" % engine_name)

    search_engine = cubes_search.create_searcher(engine_name,
                                                 browser=g.browser,
                                                 locales=g.locales,
                                                 **options)
    dimension = request.args.get("dimension")
    if not dimension:
        raise RequestError("No search dimension provided")

    query = request.args.get("query")

    if not query:
        raise RequestError("No search query provided")

    locale = g.locale or g.locales[0]

    logger.debug("searching for '%s' in %s, locale %s"
                 % (query, dimension, locale))

    search_result = search_engine.search(query, dimension, locale=locale)

    result = {
        "matches": search_result.dimension_matches(dimension),
        "dimension": dimension,
        "total_found": search_result.total_found,
        "locale": locale
    }

    if search_result.error:
        result["error"] = search_result.error

    if search_result.warning:
        result["warning"] = search_result.warning

    return jsonify(result)

