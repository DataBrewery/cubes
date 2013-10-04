# -*- coding=utf -*-
from ...model import *
from ...browser import *
from ...stores import Store
from ...providers import ModelProvider
from ...errors import *
from cubes.common import get_logger
import json
import urllib2
import urllib

class Slicer(Store):
    def __init__(self, url, **options):
        self.url = url
        self.logger = get_logger()

    def model_provider_name(self):
        return "slicer"

    def request(self, path, **kwargs):
        return json.loads(urllib2.urlopen("%s/%s" % (self.url, path)).read())

class SlicerModelProvider(ModelProvider):

    def requires_store(self):
        return True

    def list_cubes(self):
        model_desc = self.store.request('model')
        result = []
        for c in model_desc.get('cubes', []):
            result.append({
                'name': c.get('name'),
                'label': c.get('label'),
                'category': c.get('category')
            })

        return result

    def cube(self, name):
        cube_desc = self.store.request("model/cube/%s" % urllib.quote(name))

        measures = [ create_measure(m) for m in cube_desc.get('measures', []) ]
        aggregates = [ create_measure_aggregate(a) for a in cube_desc.get('aggregates', []) ]
        dimensions = [ create_dimension(d) for d in cube_desc.get('dimensions') ]

        cube = Cube(name=name, measures=measures, aggregates=aggregates, dimensions=dimensions, datastore=self.store_name,
                    mappings=None, category=cube_desc.get('category'))

        cube.info = cube_desc.get('info', {})
        return cube

    def dimension(self, name):
        raise NotImplementedError()
