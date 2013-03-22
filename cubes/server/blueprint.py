import json
from cubes.errors import CubesError, ModelError
from cubes.server.controllers import CSVGenerator
import flask
from werkzeug.local import LocalProxy

import cubes
from cubes.server.common import SlicerJSONEncoder, RequestError
try:
    import cubes_search
except ImportError:
    from cubes.common import MissingPackage
    cubes_search = None
    # SphinxSearcher = MissingPackage("cubes_search", "Sphinx search ",
    #                         source = "https://github.com/Stiivi/cubes")
    # Get cubes sphinx search backend from: https://github.com/Stiivi/cubes


API_VERSION = "1"

class SlicerBlueprint(flask.Blueprint):
    def __init__(self, workspace,  *args, **kwargs):
        super(SlicerBlueprint, self).__init__(*args, **kwargs)

        model = LocalProxy(lambda: workspace.localized_model(get_locale()))



        @self.context_processor
        def _server_info():
            info = {
                "version": cubes.__version__,
                # Backward compatibility key
                "server_version": cubes.__version__,
                "api_version": API_VERSION
            }

            return info


        @self.route('/')
        def index():
            array = [cube.name for cube in model.cubes.values()]
            if array:
                cubes = ", ".join(array)
            else:
                cubes = "<none>"
            template= '''<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
 "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
  <title>Cubes OLAP server</title>
</head>
<body>
  <h1>Cubes OLAP server</h1>
  <table id="info">
      <tr><td>Server version</td><td>{server_version}</td></tr>
      <tr><td>API version</td><td>{api_version}</td></tr>
      <tr><td>served model</td><td>{model}</td></tr>
      <tr><td>served cubes</td><td>{cubes}</td></tr>
  </table>
  <p>For more information please refer to the server
      <a href="http://packages.python.org/cubes/server.html">HTTP API documentation</a>
  </p>
</body>
</html>'''
            return flask.render_template_string(
                template,
                model=model.name,
                cubes=cubes
            )


        @self.route('/version')
        def version():
            return flask.jsonify(**_server_info())


        @self.route('/locales')
        def locales():
            return json_response(workspace.locales)


        @self.route('/model', endpoint='model')
        def _model():
            d = model.to_dict(with_mappings=False, create_label=True)

            # Add available model locales based on server configuration
            d["locales"] = workspace.locales
            return json_response(d)


        @self.route('/model/cubes', endpoint='cubes')
        def _cubes():
            cubes = [_cube_dict(cube) for cube in model.cubes.values()]
            return json_response(cubes)


        @self.route('/model/cube')
        def default_cube():
            cube = get_default_cube()
            return json_response(_cube_dict(cube))


        @self.route('/model/cube/<cube_name>')
        def cube(cube_name):
            cube = get_cube(cube_name)
            return json_response(_cube_dict(cube))


        @self.route('/model/cube/<cube_name>/dimensions')
        def list_cube_dimensions(cube_name):
            cube = get_cube(cube_name)
            dimensions = [dim.to_dict(create_label=True) for dim in cube.dimensions]
            return json_response(dimensions)


        @self.route('/model/dimension/<dim_name>')
        def dimension(dim_name):
            dim = model.dimension(dim_name)
            return json_response(dim.to_dict(create_label=True))


        @self.route('/model/dimension/<string:dim_name>/levels')
        def dimension_levels(dim_name):
            # FIXME: remove this method
            flask.current_app.logger.warn("/dimension/.../levels is depreciated")

            dim = model.dimension(dim_name)
            levels = [l.to_dict() for l in dim.hierarchy().levels]

            return json_response(levels)


        @self.route('/model/dimension/<string:dim_name>/level_names')
        def dimension_level_names(dim_name):
            # FIXME: remove this method
            flask.current_app.logger.warn("/dimension/.../level_names is depreciated")
            dim = model.dimension(dim_name)

            return json_response([a.name for a in dim.default_hierarchy.levels])

        #
        # Aggregation browser requests
        #

        @self.route('/cube/<string:cube_name>/aggregate')
        @self.route('/cube/aggregate', defaults={'cube_name': None})
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


        @self.route('/cube/facts', defaults={'cube_name':None})
        @self.route('/cube/<string:cube_name>/facts')
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


        @self.route('/cube/<string:cube_name>/fact/<string:fact_id>')
        @self.route('/cube/fact/<string:fact_id>', defaults={'cube_name':None})
        def fact(cube_name, fact_id):
            cube = get_cube(cube_name)
            browser = create_browser(cube, get_locale())
            fact = browser.fact(fact_id)

            if fact:
                return json_response(fact)
            else:
                flask.abort(404, "fact", message="No fact with id '%s'" % fact_id)


        @self.route('/cube/<string:cube_name>/dimension/<string:dimension_name>')
        @self.route('/cube/dimension/<string:dimension_name>', defaults={'cube_name':None})
        def values(cube_name, dimension_name):
            cube = get_cube(cube_name)
            browser = create_browser(cube)
            cell = prepare_cell(cube)

            depth_string = flask.request.args.get("depth")
            if depth_string:
                try:
                    depth = int(flask.request.args.get("depth"))
                except ValueError:
                    flask.abort(400, "depth should be an integer")
                    raise Exception() # only for compiler, abort raises exception

            else:
                depth = None

            try:
                dimension = cube.dimension(dimension_name)
            except KeyError:
                flask.abort(404, "Dimension '%s' was not found" % dimension_name)
                raise Exception() # only for compiler, abort raises exception

            hier_name = flask.request.args.get("hierarchy")
            hierarchy = dimension.hierarchy(hier_name)

            page, page_size = paging()
            values = browser.values(cell, dimension, depth=depth,
                                         hierarchy=hierarchy,
                                         page=page, page_size=page_size)

            depth = depth or len(hierarchy)

            result = {
                "dimension": dimension.name,
                "depth": depth,
                "data": values
            }

            return json_response(result)


        @self.route('/cube/<string:cube_name>/report', methods = ['POST'])
        def report(cube_name):
            """Create multi-query report response."""
            cube = get_cube(cube_name)
            browser = create_browser(cube)
            cell = prepare_cell(cube)

            report_request = flask.request.json

            try:
                queries = report_request["queries"]
            except KeyError:
                help = "Wrap all your report queries under a 'queries' key. The " \
                        "old documentation was mentioning this requirement, however it " \
                        "was not correctly implemented and wrong example was provided."

                raise RequestError("Report request does not contain 'queries' key",
                                            help=help)

            cell_cuts = report_request.get("cell")

            if cell_cuts:
                # Override URL cut with the one in report
                cuts = [cubes.cut_from_dict(cut) for cut in cell_cuts]
                cell = cubes.Cell(browser.cube, cuts)
                flask.current_app.logger.info("using cell from report specification (URL parameters are ignored)")

            result = browser.report(cell, queries)

            return json_response(result)


        @self.route('/cube/<string:cube_name>/cell')
        @self.route('/cube/cell', defaults={'cube_name':None})
        def cell(cube_name):
            cube = get_cube(cube_name)
            browser = create_browser(cube)
            cell = prepare_cell(cube)

            details = browser.cell_details(cell)
            cell_dict = cell.to_dict()

            for cut, detail in zip(cell_dict["cuts"], details):
                cut["details"] = detail

            return json_response(cell_dict)


        @self.route('/cube/<string:cube_name>/details')
        @self.route('/cube/details', defaults={'cube_name':None})
        def details(cube_name):
            raise RequestError("'details' request is depreciated, use 'cell' request")


        @self.route('/cube/search', defaults={'cube_name':None})
        @self.route('/cube/<string:cube_name>/search',)
        def search(cube_name):
            cube = get_cube(cube_name)
            browser = create_browser(cube)
            searcher = create_searcher(browser)


            dimension = flask.request.args.get("dimension")
            if not dimension:
                raise RequestError("No dimension provided for search")

            query = flask.request.args.get("q")
            if not query:
                query = flask.request.args.get("query")

            if not query:
                raise RequestError("No search query provided")

            locale = get_locale()
            if not locale and workspace.locales:
                locale = workspace.locales[0]

            flask.current_app.logger.debug("searching for '%s' in %s, locale %s" % (query,
                dimension, locale))

            search_result = searcher.search(query, dimension, locale=locale)

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

            return json_response(result)

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
            response = flask.make_response(json.dumps(obj, cls=SlicerJSONEncoder))
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


        def get_default_cube():
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

        def create_browser(cube, locale=None):
            """Initializes the controller:

            * tries to get cube name
            * if no cube name is specified, then tries to get default cube: either explicityly specified
              in configuration under ``[model]`` option ``cube`` or first cube in model cube list
            * assigns a browser for the controller

            """
            locale = locale if locale else get_locale()
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
            try:
                if cube_name is None:
                    return get_default_cube()
                return model.cube(cube_name)
            except ModelError, e:
                flask.abort(404, e.message)

        def get_locale():
            return flask.request.args.get('lang')

        def create_searcher(browser):
            if flask.current_app.config.get('CUBES_SEARCH_ENGINE'):
                options = flask.current_app.config.get('CUBES_SEARCH_OPTIONS')
                engine_name = flask.current_app.config['CUBES_SEARCH_ENGINE']
            else:
                raise CubesError("Search engine not configured.")

            flask.current_app.logger.debug("using search engine: %s" % engine_name)
            options = dict(options)
            searcher = cubes_search.create_searcher(engine_name,
                                                browser=browser,
                                                locales=workspace.locales,
                                                **options)