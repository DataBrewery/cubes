from werkzeug.wrappers import Response
from werkzeug.utils import redirect
from werkzeug.exceptions import NotFound

import cubes
import json

class ApplicationController(object):
    def __init__(self):
        self.model = None
        self.params = None
        self.query = None
        self.browser = None
        
    def index(self):
        return Response("CUBES OLAP Server")
                
class ModelController(ApplicationController):
    def __init__(self):
        super(ModelController, self).__init__()

    def show(self):
        string = json.dumps(self.model.to_dict())

        return Response(string)

    def dimension(self):
        dim_name = self.params["name"]
        dim = self.model.dimension(dim_name)

        string = json.dumps(dim.to_dict())

        return Response(string)
        
    def dimension_levels(self):
        dim_name = self.params["name"]
        dim = self.model.dimension(dim_name)
        levels = [l.to_dict() for l in dim.default_hierarchy.levels]

        string = json.dumps(levels)

        return Response(string)

    def dimension_level_names(self):
        dim_name = self.params["name"]
        dim = self.model.dimension(dim_name)

        string = json.dumps(dim.default_hierarchy.level_names)

        return Response(string)

class AggregationController(ApplicationController):
    def __init__(self):
        super(AggregationController, self).__init__()
