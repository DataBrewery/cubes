from cubes.server.controllers import CSVGenerator
import flask
from werkzeug.local import LocalProxy

import cubes
from cubes.server.common import SlicerJSONEncoder


API_VERSION = "1"

app = flask.Blueprint('slicer', __name__, template_folder='templates')
workspace = LocalProxy(lambda: flask.current_app.workspace)
model = LocalProxy(
    lambda: workspace.localized_model(get_locale()))


@app.context_processor
def _server_info():
    info = {
        "version": cubes.__version__,
        # Backward compatibility key
        "server_version": cubes.__version__,
        "api_version": API_VERSION
    }

    return info


@app.route('/')
def index():
    array = [cube.name for cube in model.cubes.values()]
    if array:
        cubes = ", ".join(array)
    else:
        cubes = "<none>"

    return flask.render_template(
        'index.html',
        model=model.name,
        cubes=cubes
    )


@app.route('/version')
def version():
    return flask.jsonify(**_server_info())


@app.route('/locales')
def locales():
    return json_response(workspace.locales)


@app.route('/model', endpoint='model')
def _model():
    d = model.to_dict(with_mappings=False, create_label=True)

    # Add available model locales based on server configuration
    d["locales"] = workspace.locales
    return json_response(d)


@app.route('/model/cubes', endpoint='cubes')
def _cubes():
    cubes = [_cube_dict(cube) for cube in model.cubes.values()]
    return json_response(cubes)


@app.route('/model/cube')
def default_cube():
    cube = _get_default_cube()
    return json_response(_cube_dict(cube))


@app.route('/model/cube/<cube_name>')
def cube(cube_name):
    cube = get_cube(cube_name)
    return json_response(_cube_dict(cube))


@app.route('/model/cube/<cube_name>/dimensions')
def list_cube_dimensions(cube_name):
    cube = get_cube(cube_name)
    dimensions = [dim.to_dict(create_label=True) for dim in cube.dimensions]
    return json_response(dimensions)


@app.route('/model/dimension/<dim_name>')
def dimension(dim_name):
    dim = model.dimension(dim_name)
    return json_response(dim.to_dict(create_label=True))


@app.route('/model/dimension/<string:dim_name>/levels')
def dimension_levels(dim_name):
    # FIXME: remove this method
    flask.current_app.logger.warn("/dimension/.../levels is depreciated")

    dim = model.dimension(dim_name)
    levels = [l.to_dict() for l in dim.hierarchy().levels]

    return json_response(levels)

@app.route('/model/dimension/<string:dim_name>/level_names')
def dimension_level_names(dim_name):
    # FIXME: remove this method
    flask.current_app.logger.warn("/dimension/.../level_names is depreciated")
    dim = model.dimension(dim_name)

    return json_response([a.name for a in dim.default_hierarchy.levels])

#
# Aggregation browser requests
#

@app.route('/cube/<string:cube_name>/aggregate')
def aggregate(cube_name):
    cube = get_cube(cube_name)
    browser = create_browser(cube, get_locale())
    cell = prepare_cell(cube)

    ddlist = flask.request.args.getlist("drilldown")

    drilldown = []

    if ddlist:
        for ddstring in ddlist:
            drilldown += ddstring.split("|")

    page, page_size = paging()
    result = browser.aggregate(cell, drilldown=drilldown,
                                    page=page,
                                    page_size=page_size,
                                    order=order())

    return json_response(result)

@app.route('/cube/<string:cube_name>/facts')
def facts(cube_name):
    cube = get_cube(cube_name)
    browser = create_browser(cube, get_locale())
    cell = prepare_cell(cube)

    format_ = flask.request.args.get("format")
    format_ = format_.lower() if format_ else "json"

    fields_str = flask.request.args.get("fields")
    if fields_str:
        fields = fields_str.lower().split(',')
    else:
        fields = None

    page, page_size = paging()
    result = browser.facts(cell, order = order(),
                                page = page,
                                page_size = page_size)

    if format_ == "json":
        return json_response(result)
    elif format_ == "csv":
        if not fields:
            fields = result.labels
        generator = CSVGenerator(result, fields)

        return csv_response(generator)
    else:
        flask.abort(400, "unknown response format '%s'" % format_)

@app.route('/cube/<string:cube_name>/fact/<string:fact_id>')
def fact(cube_name, fact_id):
    cube = get_cube(cube_name)
    browser = create_browser(cube, get_locale())
    fact = browser.fact(fact_id)

    if fact:
        return json_response(fact)
    else:
        flask.abort(404, "fact", message="No fact with id '%s'" % fact_id)

#     Rule('/cube/<string:cube>/fact/<string:fact_id>',
#                         endpoint = (controllers.CubesController, 'fact')),
#     Rule('/cube/<string:cube>/dimension/<string:dimension_name>',
#                         endpoint = (controllers.CubesController, 'values')),
#     Rule('/cube/<string:cube>/report', methods = ['POST'],
#                         endpoint = (controllers.CubesController, 'report')),
#     Rule('/cube/<string:cube>/cell',
#                         endpoint = (controllers.CubesController, 'cell_details')),
#     Rule('/cube/<string:cube>/details',
#                         endpoint = (controllers.CubesController, 'details')),
#     # Use default cube (specified in config as: [model] cube = ... )
#     Rule('/aggregate',
#                         endpoint = (controllers.CubesController, 'aggregate'),
#                         defaults={"cube":None}),
#     Rule('/facts',
#                         endpoint = (controllers.CubesController, 'facts'),
#                         defaults={"cube":None}),
#     Rule('/fact/<string:fact_id>',
#                         endpoint = (controllers.CubesController, 'fact'),
#                         defaults={"cube":None}),
#     Rule('/dimension/<string:dimension_name>',
#                         endpoint=(controllers.CubesController, 'values'),
#                         defaults={"cube":None}),
#     Rule('/report', methods = ['POST'],
#                         endpoint = (controllers.CubesController, 'report'),
#                         defaults={"cube":None}),
#     Rule('/cell',
#                         endpoint = (controllers.CubesController, 'cell_details'),
#                         defaults={"cube":None}),
#     Rule('/details',
#                         endpoint = (controllers.CubesController, 'details'),
#                         defaults={"cube":None}),
#     #
#     # Other utility requests
#     #
#     Rule('/cube/<string:cube>/search',
#                         endpoint = (controllers.SearchController, 'search')),
#
#     Rule('/search',
#                         endpoint = (controllers.SearchController, 'search'),
#                         defaults={"cube":None})
def json_response(obj):
    response = flask.make_response(flask.json.dumps(obj, cls=SlicerJSONEncoder))
    response.mimetype = 'application/json'
    return response

def csv_response(csv):
    response = flask.make_response('\n'.join(csv))
    response.mimetype='text/csv'
    return response


def _cube_dict(cube):
    d = cube.to_dict(expand_dimensions=True,
                     with_mappings=False,
                     full_attribute_names=True,
                     create_label=True
    )

    return d


def _get_default_cube():
    if flask.current_app.config.get('SLICER_DEFAULT_CUBE'):
        flask.current_app.logger.debug(
            "using default cube specified in cofiguration")
        cube_name = flask.current_app.config.get('SLICER_DEFAULT_CUBE')
        cube = get_cube(cube_name)
    else:
        flask.current_app.logger.debug("using first cube from model")
        cube = model.cubes.values()[0]
        cube_name = cube.name

    return cube

def create_browser(cube, locale):
    """Initializes the controller:

    * tries to get cube name
    * if no cube name is specified, then tries to get default cube: either explicityly specified
      in configuration under ``[model]`` option ``cube`` or first cube in model cube list
    * assigns a browser for the controller

    """
    flask.current_app.logger.info("browsing cube '%s' (locale: %s)" % (cube.name, locale))
    browser = workspace.browser(cube, locale)
    return browser

def prepare_cell(cube):
    cut_strings = flask.request.args.getlist("cut")

    if cut_strings:
        cuts = []
        for cut_string in cut_strings:
            flask.current_app.logger.debug("preparing cell from string: '%s'" % cut_string)
            cuts += cubes.cuts_from_string(cut_string)
    else:
        flask.current_app.logger.debug("preparing cell as whole cube")
        cuts = []

    cell = cubes.Cell(cube, cuts)
    return cell

def paging():
    page = 1
    if "page" in flask.request.args:
        try:
            page = int(flask.request.args.get("page"))
        except ValueError:
            flask.abort(400, "'page' should be a number")

    page_size = None
    if "pagesize" in flask.request.args:
        try:
            page_size = int(flask.request.args.get("pagesize"))
        except ValueError:
            raise flask.abort(400, "'pagesize' should be a number")

    return page, page_size

def order():
    order = []
    for orders in flask.request.args.getlist("order"):
        for order in orders.split(","):
            split = order.split(":")
            if len(split) == 1:
                order.append((order, None))
            else:
                order.append((split[0], split[1]))

    return order

def get_cube(cube_name):
    return model.cube(cube_name)

def get_locale():
    return flask.request.args.get('lang')