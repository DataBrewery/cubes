# -*- coding: utf-8 -*-
from flask import Blueprint, Response, request, g, current_app, url_for, safe_join, make_response
from flask import render_template, redirect
from jinja2 import Template
import json, re
from functools import wraps
import sys
import traceback

from ..workspace import Workspace, SLICER_INFO_KEYS
from ..cells import Cell, cut_from_dict
from ..browser import SPLIT_DIMENSION_NAME
from ..errors import *
from ..formatters import JSONLinesGenerator, csv_generator
from .. import ext
from ..logging import get_logger
from .logging import configured_request_log_handlers, RequestLogger
from .logging import AsyncRequestLogger
from .errors import *
from .decorators import *
from .local import *
from .auth import NotAuthenticated

from collections import OrderedDict

from cubes import __version__

# TODO: missing features from the original Werkzeug Slicer:
# * /locales and localization
# * default cube: /aggregate
# * caching
# * root / index
# * response.headers.add("Access-Control-Allow-Origin", "*")

try:
    import cubes_search
except ImportError:
    cubes_search = None

__all__ = (
    "slicer",
    "API_VERSION"
)

API_VERSION = 2

# Cross-origin resource sharing – 20 days cache
CORS_MAX_AGE = 1728000

slicer = Blueprint("slicer", __name__, template_folder="templates")

# Before
# ------

def _store_option(config, option, default, type_=None, allowed=None,
                      section="server"):
    """Copies the `option` into the application config dictionary. `default`
    is a default value, if there is no such option in `config`. `type_` can be
    `bool`, `int` or `string` (default). If `allowed` is specified, then the
    option should be only from the list of allowed options, otherwise a
    `ConfigurationError` exception is raised.
    """

    if config.has_option(section, option):
        if type_ == "bool":
            value = config.getboolean(section, option)
        elif type_ == "int":
            value = config.getint(section, option)
        else:
            value = config.get(section, option)
    else:
        value = default

    if allowed and value not in allowed:
        raise ConfigurationError("Invalued value '%s' for option '%s'"
                                 % (value, option))

    setattr(current_app.slicer, option, value)


@slicer.record_once
def initialize_slicer(state):
    """Create the workspace and configure the application context from the
    ``slicer.ini`` configuration."""

    with state.app.app_context():
        config = state.options["config"]

        logger = get_logger()
        # Create workspace and other app objects
        # We avoid pollution of the current_app context, as we are a Blueprint
        params = CustomDict()
        current_app.slicer = params
        current_app.slicer.config = config

        # FIXME: this is a workaround, see Workspace note about _options
        if "cubes_root" in state.options:
            _options = {"cubes_root": state.options["cubes_root"]}
        else:
            _options = {}

        if not hasattr(current_app, 'cubes_workspace'):
            current_app.cubes_workspace = Workspace(config, **_options)

        # Configure the application
        # FIXME XXX this shouldn't be in the "server" section
        _store_option(config, "prettyprint", False, "bool")
        _store_option(config, "json_record_limit", 1000, "int")
        _store_option(config, "hide_private_cuts", False, "bool")
        _store_option(config, "allow_cors_origin", None, "str")
        _store_option(config, "visualizer", None, "str")

        _store_option(config, "authentication", "none")

        method = current_app.slicer.authentication
        if method is None or method == "none":
            current_app.slicer.authenticator = None
        else:
            if config.has_section("authentication"):
                options = dict(config.items("authentication"))
            else:
                options = {}

            current_app.slicer.authenticator = ext.authenticator(method,
                                                                        **options)
        logger.debug("Server authentication method: %s" % (method or "none"))

        if not current_app.slicer.authenticator and workspace.authorizer:
            logger.warn("No authenticator specified, but workspace seems to "
                        "be using an authorizer")

        # Collect query loggers
        handlers = configured_request_log_handlers(config)

        if config.has_option('server', 'asynchronous_logging'):
            async_logging = config.getboolean("server", "asynchronous_logging")
        else:
            async_logging = False

        if async_logging:
            current_app.slicer.request_logger = AsyncRequestLogger(handlers)
        else:
            current_app.slicer.request_logger = RequestLogger(handlers)

# Before and After
# ================

@slicer.before_request
def process_common_parameters():
    # TODO: setup language

    # Copy from the application context
    g.json_record_limit = current_app.slicer.json_record_limit

    if "prettyprint" in request.args:
        g.prettyprint = str_to_bool(request.args.get("prettyprint"))
    else:
        g.prettyprint = current_app.slicer.prettyprint


@slicer.before_request
def prepare_authorization():
    if current_app.slicer.authenticator:
        try:
            identity = current_app.slicer.authenticator.authenticate(request)
        except NotAuthenticated as e:
            raise NotAuthenticatedError
    else:
        identity = None

    # Authorization
    # -------------
    g.auth_identity = identity


# Error Handler
# =============

@slicer.errorhandler(UserError)
def user_error_handler(e):
    error_type = e.__class__.error_type
    error = OrderedDict()
    error["error"] = error_type
    error["message"] = str(e)

    if hasattr(e, "hint") and e.hint:
        error["hint"] = e.hint

    if hasattr(e, "to_dict"):
        error.update(e.to_dict())

    code = server_error_codes.get(error_type, 400)

    return jsonify(error), code

@slicer.errorhandler(404)
def page_not_found(e):
    error = {
        "error": "not_found",
        "message": "The requested URL was not found on the server.",
        "hint": "If you entered the URL manually please check your "
                "spelling and try again."
    }
    return jsonify(error), 404

@slicer.errorhandler(InternalError)
def server_error(e):

    (exc_type, exc_value, exc_traceback) = sys.exc_info()
    exc_name = exc_type.__name__
    logger.error("Internal Cubes error ({}): {}".format(exc_name, exc_value))

    tb = traceback.format_exception(exc_type, exc_value,
                                    exc_traceback)
    logger.debug("Exception stack trace:\n{}".format("".join(tb)))

    error = {
        "error": "internal_server_error",
        "message": "Internal server error",
        "hint": "Server administrators can learn more about the error from "
                "the error logs (even more if they have 'debug' level)"
    }

    return jsonify(error), 500

# Endpoints
# =========

@slicer.route("/")
def show_index():
    info = get_info()
    has_about = any(key in info for key in SLICER_INFO_KEYS)

    return render_template("index.html",
                           has_about=has_about,
                           **info)


@slicer.route("/version")
def show_version():
    info = {
        "version": __version__,
        # Backward compatibility key
        "server_version": __version__,
        "api_version": API_VERSION
    }
    return jsonify(info)


def get_info():
    if workspace.info:
        info = OrderedDict(workspace.info)
    else:
        info = OrderedDict()

    info["json_record_limit"] = current_app.slicer.json_record_limit
    info["cubes_version"] = __version__
    info["timezone"] = workspace.calendar.timezone_name
    info["first_weekday"] = workspace.calendar.first_weekday
    info["api_version"] = API_VERSION

    # authentication
    authinfo = {}

    authinfo["type"] = (current_app.slicer.authentication or "none")

    if g.auth_identity:
        authinfo['identity'] = g.auth_identity

    if current_app.slicer.authenticator:
        ainfo = current_app.slicer.authenticator.info_dict(request)
        authinfo.update(ainfo)

    info['authentication'] = authinfo

    return info

@slicer.route("/info")
def show_info():
    return jsonify(get_info())


@slicer.route("/cubes")
def list_cubes():
    cube_list = workspace.list_cubes(g.auth_identity)
    # TODO: cache per-identity
    return jsonify(cube_list)


@slicer.route("/cube/<cube_name>/model")
@requires_cube
def cube_model(cube_name):
    if workspace.authorizer:
        hier_limits = workspace.authorizer.hierarchy_limits(g.auth_identity,
                                                            cube_name)
    else:
        hier_limits = None

    response = g.cube.to_dict(expand_dimensions=True,
                              with_mappings=False,
                              full_attribute_names=True,
                              create_label=True,
                              hierarchy_limits=hier_limits)

    response["features"] = workspace.cube_features(g.cube)

    return jsonify(response)


@slicer.route("/cube/<cube_name>/aggregate")
@requires_browser
@log_request("aggregate", "aggregates")
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

    # Hide cuts that were generated internally (default: don't)
    if current_app.slicer.hide_private_cuts:
        result.cell = result.cell.public_cell()

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
    generator = csv_generator(result,
                             fields,
                             include_header=bool(header),
                             header=header)

    headers = {"Content-Disposition": 'attachment; filename="aggregate.csv"'}
    return Response(generator,
                    mimetype='text/csv',
                    headers=headers)


@slicer.route("/cube/<cube_name>/facts")
@requires_browser
@log_request("facts", "fields")
def cube_facts(cube_name):
    # Request parameters
    fields_str = request.args.get("fields")
    if fields_str:
        fields = fields_str.split(',')
    else:
        fields = None

    # fields contain attribute names
    if fields:
        attributes = g.cube.get_attributes(fields)
    else:
        attributes = g.cube.all_fact_attributes

    # Construct the field list
    fields = [attr.ref for attr in attributes]

    # Get the result
    facts = g.browser.facts(g.cell,
                             fields=fields,
                             order=g.order,
                             page=g.page,
                             page_size=g.page_size)

    # Add cube key to the fields (it is returned in the result)
    fields.insert(0, g.cube.key or "__fact_key__")

    # Construct the header
    labels = [attr.label or attr.name for attr in attributes]
    labels.insert(0, g.cube.key or "__fact_key__")

    return formatted_response(facts, fields, labels)

@slicer.route("/cube/<cube_name>/fact/<fact_id>")
@requires_browser
def cube_fact(cube_name, fact_id):
    fact = g.browser.fact(fact_id)

    if fact:
        return jsonify(fact)
    else:
        raise NotFoundError(fact_id, "fact",
                            message="No fact with id '%s'" % fact_id)


@slicer.route("/cube/<cube_name>/members/<dimension_name>")
@requires_browser
@log_request("members")
def cube_members(cube_name, dimension_name):
    # TODO: accept level name
    depth = request.args.get("depth")
    level = request.args.get("level")

    if depth and level:
        raise RequestError("Both depth and level provided, use only one "
                           "(preferably level)")

    if depth:
        try:
            depth = int(depth)
        except ValueError:
            raise RequestError("depth should be an integer")

    try:
        dimension = g.cube.dimension(dimension_name)
    except KeyError:
        raise NotFoundError(dimension_name, "dimension",
                            message="Dimension '%s' was not found" % dimension_name)

    hier_name = request.args.get("hierarchy")
    hierarchy = dimension.hierarchy(hier_name)

    if not depth and not level:
        depth = len(hierarchy)
    elif level:
        depth = hierarchy.level_index(level) + 1

    values = g.browser.members(g.cell,
                               dimension,
                               depth=depth,
                               hierarchy=hierarchy,
                               page=g.page,
                               page_size=g.page_size)

    result = {
        "dimension": dimension.name,
        "hierarchy": hierarchy.name,
        "depth": len(hierarchy) if depth is None else depth,
        "data": values
    }

    # Collect fields and labels
    attributes = []
    for level in hierarchy.levels_for_depth(depth):
        attributes += level.attributes

    fields = [attr.ref for attr in attributes]
    labels = [attr.label or attr.name for attr in attributes]

    return formatted_response(result, fields, labels, iterable=values)


@slicer.route("/cube/<cube_name>/cell")
@requires_browser
def cube_cell(cube_name):
    details = g.browser.cell_details(g.cell)

    if not g.cell:
        g.cell = Cell(g.cube)

    cell_dict = g.cell.to_dict()
    for cut, detail in zip(cell_dict["cuts"], details):
        cut["details"] = detail

    return jsonify(cell_dict)


@slicer.route("/cube/<cube_name>/report", methods=["GET", "POST"])
@requires_browser
def cube_report(cube_name):
    report_request = json.loads(request.data)

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

        if workspace.authorizer:
            cell = workspace.authorizer.restricted_cell(g.auth_identity,
                                                        cube=g.cube,
                                                        cell=cell)
    else:
        if not g.cell:
            cell = Cell(g.cube)
        else:
            cell = g.cell

    result = g.browser.report(cell, queries)

    return jsonify(result)


@slicer.route("/cube/<cube_name>/search")
def cube_search(cube_name):
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


@slicer.route("/logout")
def logout():
    if current_app.slicer.authenticator:
        return current_app.slicer.authenticator.logout(request, g.auth_identity)
    else:
        return "logged out"


@slicer.route("/visualizer/")
@slicer.route("/visualizer/index.html")
def get_visualizer():
    viz = current_app.slicer.visualizer

    if viz:
        return redirect(viz)
    else:
        raise PageNotFoundError("Visualizer not configured")

@slicer.after_request
def add_cors_headers(response):
    """Add Cross-origin resource sharing headers."""
    origin = current_app.slicer.allow_cors_origin
    if origin and len(origin):
        if request.method == 'OPTIONS':
            response.headers['Access-Control-Allow-Headers'] = 'X-Requested-With'
            # OPTIONS preflight requests need to receive origin back instead of wildcard
        if origin == '*':
            response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', origin)
        else:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Max-Age'] = CORS_MAX_AGE
    return response
