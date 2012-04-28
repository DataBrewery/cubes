try:
    from werkzeug.wrappers import Response
    from werkzeug.utils import redirect
    from werkzeug.exceptions import NotFound
except:
    from cubes.common import MissingPackage
    _missing = MissingPackage("werkzeug", "Slicer server")
    Response = redirect = NotFound = _missing

import logging
import cubes
import os.path
from .. import common

import json

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
            raise common.RequestError("No translation for language '%s'" % self.locale)
        
    def index(self):
        handle = open(os.path.join(common.TEMPLATE_PATH, "index.html"))
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
            "api_version": common.API_VERSION
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
        
        encoder = common.SlicerJSONEncoder(indent = indent)
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
            return json.loads(self.request.data)
        else:
            raise common.RequestError("JSON requested from unknown content-type '%s'" % content_type)
