from werkzeug.wrappers import Response
from werkzeug.utils import redirect
from werkzeug.exceptions import NotFound
import sqlalchemy
import logging
import cubes
import os.path
from .. import common

import json

class ApplicationController(object):
    def __init__(self, app, config):

        self.app = app
        self.engine = app.engine
        self.master_model = app.model
        self.logger = app.logger

        self.config = config

        if config.has_option("server","json_record_limit"):
            self.json_record_limit = config.get("server","json_record_limit")
        else:
            self.json_record_limit = 1000
            
        self.params = None
        self.query = None
        self.locale = None
        self.prettyprint = None
        self.browser = None
        self.model = None

    def _localize_model(self):
        """Tries to translate the model. Looks for language in configuration file under 
        ``[translations]``, if no translation is provided, then model remains untouched."""

        self.logger.debug("localization requested (model locale: %s)" % self.model.locale)
        # Do not translate if already translated
        if self.model.locale == self.locale:
            self.logger.debug("no localization needed")
            return

        if self.config.has_option("translations", self.locale):
            self.logger.debug("translating model to %s" % self.locale)
            path = self.config.get("translations", self.locale)
            handle = open(path)
            trans = json.load(handle)
            handle.close()
            self.model = self.master_model.localize(trans)
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
            "server_version": common.VERSION,
            "api_version": common.API_VERSION
        }
        return info
        
    def version(self):
        return self.json_response(self.server_info())

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
            if ppflag.lower() in ["true", "yes", "1"]:
                self.prettyprint = True
            else:
                self.prettyprint = False
        else:
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

class Workspace(object):
    """OLAP Workspace for serving browsers."""
    def __init__(self, arg):
        super(Workspace, self).__init__()
        self.arg = arg
        