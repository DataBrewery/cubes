from werkzeug.wrappers import Response
from werkzeug.utils import redirect
from werkzeug.exceptions import NotFound
import sqlalchemy

import cubes
import json

class ApplicationController(object):
    def __init__(self, config):
        self.model = cubes.load_model(config["model"])
        self.cube_name = config["cube"]
        self.cube = self.model.cube(self.cube_name)

        if "view" in config:
            self.view_name = config["view"]
        else:
            self.view_name = self.cube_name

        self.dburl = config["dburl"]

        self.params = None
        self.query = None
        self.browser = None
        
    def index(self):
        return Response("CUBES OLAP Server version 0.1")
    
    def json_response(self, obj):
        string = json.dumps(obj)
        return Response(string, mimetype='application/json')
        
    def initialize(self):
        pass
        
    def finalize(self):
        pass
        
class ModelController(ApplicationController):

    def show(self):
        return self.json_response(self.model.to_dict())

    def dimension(self):
        dim_name = self.params["name"]

        dim = self.model.dimension(dim_name)
        return self.json_response(dim.to_dict())
        
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

class AggregationController(ApplicationController):
    def initialize(self):

        self.engine = sqlalchemy.create_engine(self.dburl)
        self.connection = self.engine.connect()

        self.browser = cubes.backends.SimpleSQLBrowser(self.cube, self.connection, self.view_name)

    def finalize(self):
        self.connection.close()
        
    def aggregate(self):
        cut_string = self.request.args.get("cut")
        print "CUT_STRING: %s" % self.request.args.keys()
        if cut_string:
            cuts = cubes.cuts_from_string(cut_string)
        else:
            cuts = []

        cuboid = cubes.Cuboid(self.browser, cuts)
        
        result = self.browser.aggregate(cuboid)
        print "RESULT: %s" % result
        return Response(result.as_json())
        # return self.json_response(result.__dict__())
