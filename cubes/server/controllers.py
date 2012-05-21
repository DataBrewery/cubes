try:
    from werkzeug import __version__ as werkzeug_version
    from slicer import Slicer, run_server
except ImportError:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Slicer = run_server = _missing

__all__ = (
    "Slicer",
    "run_server",
    "API_VERSION"
)

import logging
import cubes
import os.path
import json
import cStringIO
import csv
import codecs

from .common import API_VERSION, TEMPLATE_PATH
from .common import RequestError, ServerError, NotFoundError
from .common import SlicerJSONEncoder

try:
    from werkzeug.wrappers import Response
    from werkzeug.utils import redirect
    from werkzeug.exceptions import NotFound
except:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Response = redirect = NotFound = _missing

try:
    from cubes_search.sphinx import SphinxSearcher
except:
    from cubes.common import MissingPackage
    SphinxSearcher = None
    # SphinxSearcher = MissingPackage("cubes_search", "Sphinx search ", 
    #                         source = "https://github.com/Stiivi/cubes")
    # Get cubes sphinx search backend from: https://github.com/Stiivi/cubes

class ApplicationController(object):
    def __init__(self, app, config):

        self.app = app
        self.master_model = app.model
        self.logger = app.logger

        self.config = config

        if config.has_option("server","json_record_limit"):
            self.json_record_limit = config.get("server","json_record_limit")
        else:
            self.json_record_limit = 1000

        if config.has_option("server","prettyprint"):
            self.prettyprint = config.getboolean("server","prettyprint")
        else:
            self.prettyprint = False
            
        self.params = None
        self.query = None
        self.locale = None
        self.browser = None
        self.model = None

    def _localize_model(self):
        """Tries to translate the model. Looks for language in configuration file under 
        ``[translations]``, if no translation is provided, then model remains untouched."""

        # FIXME: Rewrite this to make it thread safer

        self.logger.debug("localization to '%s' (current: '%s') requested (has: %s)" % (self.locale, self.model.locale, self.app.model_localizations.keys()))

        if self.locale in self.app.model_localizations:
            self.logger.debug("localization '%s' found" % self.locale)
            self.model = self.app.model_localizations[self.locale]

        elif self.locale == self.master_model.locale:
            self.app.model_localizations[self.locale] = self.master_model
            self.model = self.master_model

        elif self.config.has_option("translations", self.locale):
            path = self.config.get("translations", self.locale)
            self.logger.debug("translating model to '%s' translation path: %s" % (self.locale, path))
            with open(path) as handle:
                trans = json.load(handle)
            model = self.master_model.localize(trans)
                
            self.app.model_localizations[self.locale] = model
            self.model = model

        else:
            raise RequestError("No translation for language '%s'" % self.locale)
        
    def index(self):
        handle = open(os.path.join(TEMPLATE_PATH, "index.html"))
        template = handle.read()
        handle.close()
        
        context = {}
        context.update(self.server_info())

        context["model"] = self.model.name
        array = []
        for cube in self.model.cubes.values():
            array.append(cube.name)
            
        if array:
            context["cubes"] = ", ".join(array)
        else:
            context["cubes"] = "<none>"
        
        doc = template.format(**context)
        
        return Response(doc, mimetype = 'text/html')

    def server_info(self):
        info = {
            "version": cubes.__version__,
            # Backward compatibility key
            "server_version": cubes.__version__, 
            "api_version": API_VERSION
        }
        return info
        
    def version(self):
        return self.json_response(self.server_info())

    def locales(self):
        """Return list of available model locales"""
        return self.json_response(self.app.locales)

    def json_response(self, obj):
        if self.prettyprint:
            indent = 4
        else:
            indent = None
        
        encoder = SlicerJSONEncoder(indent = indent)
        encoder.iterator_limit = self.json_record_limit
        reply = encoder.iterencode(obj)

        return Response(reply, mimetype='application/json')
    
    @property
    def args(self):
        return self._args
        
    @args.setter
    def args(self, args):
        self._args = args

        if "page" in args:
            self.page = int(args.get("page"))
        else:
            self.page = None
        if "pagesize" in args:
            self.page_size = int(args.get("pagesize"))
        else:
            self.page_size = None

        # Collect orderings:
        # order is specified as order=<field>[:<direction>]
        # examples:
        #
        #     order=date.year     # order by year, unspecified direction
        #     order=date.year:asc # order by year ascending
        #

        self.order = []
        for order in args.getlist("order"):
            split = order.split(":")
            if len(split) == 1:
                self.order.append( (order, None) )
            else:
                self.order.append( (split[0], split[1]) )

        ppflag = args.get("prettyprint")
        if ppflag:
            if ppflag.lower() in ["true", "yes", "1", "on"]:
                self.prettyprint = True
            elif ppflag.lower() in ["false", "no", "0", "off"]:
                self.prettyprint = False

        self.locale = args.get("lang")
        self.model = self.master_model
        
        if self.locale:
            self._localize_model()
                
    def finalize(self):
        pass
    
    def initialize(self):
        pass
    
    def error(self, message = None, exception = None, status = None):
        if not message:
            message = "An unknown error occured"
            
        error = {}
        error["message"] = message
        if exception:
            error["reason"] = str(exception)

        string = json.dumps({"error": error},indent = 4)
        
        if not status:
            status = 500
        
        return Response(string, mimetype='application/json', status = status)

    def json_request(self):
        content_type = self.request.headers.get('content-type')
        if content_type == 'application/json':
            try:
                result = json.loads(self.request.data)
            except Exception as e:
                raise RequestError("Problem loading request JSON data", reason=str(e))
            return result
        else:
            raise RequestError("JSON requested from unknown content-type '%s'" % content_type)


class ModelController(ApplicationController):

    def show(self):
        d = self.model.to_dict(with_mappings = False)

        # Add available model locales based on server configuration
        d["locales"] = self.app.locales;
        return self.json_response(d)

    def dimension(self):
        dim_name = self.params["name"]

        dim = self.model.dimension(dim_name)
        return self.json_response(dim.to_dict())

    def _cube_dict(self, cube):
        d = cube.to_dict(expand_dimensions = True, 
                         with_mappings = False,
                         full_attribute_names = True
                         )

        return d

    def get_default_cube(self):
        return self.json_response(self._cube_dict(self.cube))

    def get_cube(self):
        cube_name = self.params["name"]

        cube = self.model.cube(cube_name)
        return self.json_response(self._cube_dict(cube))

    def dimension_levels(self):
        dim_name = self.params["name"]
        dim = self.model.dimension(dim_name)
        levels = [l.to_dict() for l in dim.default_hierarchy.levels]

        string = json.dumps(levels)

        return Response(string)

    def dimension_level_names(self):
        dim_name = self.params["name"]
        dim = self.model.dimension(dim_name)

        return self.json_response(dim.default_hierarchy.level_names)


class CSVGenerator(object):
    def __init__(self, records, fields, include_header = True, 
                dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.include_header = include_header
        self.records = records
        self.fields = fields
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.encoder = codecs.getincrementalencoder(encoding)()

    def csvrows(self):
        if self.include_header:
            yield self._row_string(self.fields)

        for record in self.records:
            row = []
            for field in self.fields:
                value = record.get(field)
                if type(value) == unicode or type(value) == str:
                    row.append(value.encode("utf-8"))
                elif value:
                    row.append(unicode(value))
                else:
                    row.append(None)

            yield self._row_string(row)

    def _row_string(self, row):
        self.writer.writerow(row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # empty queue
        self.queue.truncate(0)

        return data

class UnicodeCSVWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.

    From: <http://docs.python.org/lib/csv-examples.html>
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        new_row = []
        for value in row:
            if type(value) == unicode or type(value) == str:
                new_row.append(value.encode("utf-8"))
            elif value:
                new_row.append(unicode(value))
            else:
                new_row.append(None)

        self.writer.writerow(new_row)
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

class CubesController(ApplicationController):
    def initialize(self):
        """Initializes the controller:

        * tries to get cube name
        * if no cube name is specified, then tries to get default cube: either explicityly specified
          in configuration under ``[model]`` option ``cube`` or first cube in model cube list
        * assigns a browser for the controller

        """

        # FIXME: keep or remove default cube?
        cube_name = self.params.get("cube")

        if cube_name:
            self.cube = self.model.cube(cube_name)
        else:
            if self.config.has_option("model", "cube"):
                self.logger.debug("using default cube specified in cofiguration")
                cube_name = self.config.get("model", "cube")
                self.cube = self.model.cube(cube_name)
            else:
                self.logger.debug("using first cube from model")
                self.cube = self.model.cubes.values()[0]
                cube_name = self.cube.name

        self.logger.info("browsing cube '%s' (locale: %s)" % (cube_name, self.locale))
        self.browser = self.app.workspace.browser_for_cube(self.cube, self.locale)

    def prepare_cell(self):
        cut_string = self.args.get("cut")

        if cut_string:
            self.logger.debug("preparing cell for cut string: '%s'" % cut_string)
            cuts = cubes.cuts_from_string(cut_string)
        else:
            self.logger.debug("preparing cell for whole cube")
            cuts = []

        self.cell = cubes.Cell(self.cube, cuts)

    def aggregate(self):
        self.prepare_cell()

        drilldown = self.args.getlist("drilldown")
        dic_drilldown = {}

        # Allow dimension:level specification for drilldown

        if drilldown:
            for drill_dim in drilldown:
                split = drill_dim.split(":")
                dic_drilldown[split[0]] = split[1] if len(split) >= 2 else None

        result = self.browser.aggregate(self.cell, drilldown = dic_drilldown,
                                        page = self.page,
                                        page_size = self.page_size,
                                        order = self.order)

        return self.json_response(result)

    def facts(self):
        self.prepare_cell()

        format = self.args.get("format")
        if format:
            format = format.lower()
        else:
            format = "json"

        fields_str = self.args.get("fields")
        if fields_str:
            fields = fields_str.lower().split(',')
        else:
            fields = None

        result = self.browser.facts(self.cell, order = self.order,
                                    page = self.page,
                                    page_size = self.page_size)

        if format == "json":
            return self.json_response(result)
        elif format == "csv":
            if not fields:
                fields = result.labels
            generator = CSVGenerator(result, fields)
            return Response(generator.csvrows(),
                            mimetype='text/csv')
        else:
            raise RequestError("unknown response format '%s'" % format)

    def fact(self):
        fact_id = self.params["id"]

        fact = self.browser.fact(fact_id)

        if fact:
            return self.json_response(fact)
        else:
            return self.error("No fact with id=%s" % fact_id, status = 404)

    def values(self):
        self.prepare_cell()

        dim_name = self.params["dimension"]
        depth_string = self.args.get("depth")
        if depth_string:
            try:
                depth = int(self.args.get("depth"))
            except ValueError:
                raise RequestError("depth should be an integer")
        else:
            depth = None

        try:
            dimension = self.cube.dimension(dim_name)
        except KeyError:
            raise NotFoundError(dim_name, "dimension",
                                        message = "Dimension '%s' was not found" % dim_name)

        values = self.browser.values(self.cell, dimension, depth = depth, page = self.page, page_size = self.page_size)

        result = {
            "dimension": dimension.name,
            "depth": depth,
            "data": values
        }

        return self.json_response(result)

    def report(self):
        """Create multi-query report response."""
        self.prepare_cell()

        report_request = self.json_request()

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
            cell = cubes.Cell(self.browser.cube, cuts)
            self.logger.info("using cell from report specification (URL parameters are ignored)")
        else:
            cell = self.cell

        result = self.browser.report(cell, queries)

        return self.json_response(result)

    def details(self):
        self.prepare_cell()

        result = self.browser.cell_details(self.cell)

        return self.json_response(result)


class SearchController(ApplicationController):
    """docstring for SearchController

    Config options:

    sql_index_table: table name
    sql_schema
    sql_url
    search_backend: sphinx otherwise we raise exception.

    """        

    def initialize(self):
        # FIXME: remove this (?)
        cube_name = self.params.get("cube")
        if not cube_name:
            cube_name = self.config.get("model", "cube")

        self.cube = self.model.cube(cube_name)
        self.browser = self.app.workspace.browser_for_cube(self.cube, locale = self.locale)

        if self.config.has_option("sphinx", "host"):
            self.sphinx_host = self.config.get("sphinx","host")
        else:
            self.sphinx_host = None

        if self.config.has_option("sphinx", "port"):
            self.sphinx_port = self.config.getint("sphinx","port")
        else:
            self.sphinx_port = None

    def search(self):
        if not SphinxSearcher:
            raise ServerError("Search extension cubes_search is not installed")

        sphinx = SphinxSearcher(self.browser, self.sphinx_host, self.sphinx_port)

        dimension = self.args.get("dimension")
        if not dimension:
            return self.error("No dimension provided")

        query = self.args.get("q")
        if not query:
            query = self.args.get("query")

        if not query:
            return self.error("No query provided")

        zipped = self.args.get("_zip")

        locale_tag = 0
        if self.locale:
            for (i, locale) in enumerate(self.app.locales):
                if locale == self.locale:
                    locale_tag = i
                    break


        search_result = sphinx.search(query, dimension, locale_tag = locale_tag)

        # FIXME: remove "values" - backward compatibility key
        result = {
            "values": None,
            "matches": search_result.dimension_matches(dimension),
            "dimension": dimension,
            "total_found": search_result.total_found,
            "locale": self.locale,
            "_locale_tag": locale_tag,
            "_browser_locale": self.browser.locale
        }

        if search_result.error:
            result["error"] = search_result.error
        if search_result.warning:
            result["warning"] = search_result.warning

        return self.json_response(result)

