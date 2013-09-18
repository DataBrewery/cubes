# -*- coding=utf -*-
from ...model import *
from ...browser import *
from ...stores import Store
from ...errors import *
from .mixpanel import *
from string import capwords

DIMENSION_COUNT_LIMIT = 100

time_dimension_md = {
    "name": "time",
    "levels": ["year", "month", "day", "hour"],
    "hierarchies": [
        {"name":"mdh", "levels": ["year", "month", "day", "hour"]}
    ]
}

_time_dimension = create_dimension(time_dimension_md)

class MixpanelModelProvider(ModelProvider):
    def cube(self, name):
        result = self.store.request(["events", "properties", "top"],
                            {"event":name, "limit":DIMENSION_COUNT_LIMIT})
        if not result:
            raise NoSuchCubeError(name)

        dims = result.keys()
        dims.append("time")

        measures = attribute_list(["total", "uniques"])

        cube = Cube(name=name,
                    measures=measures,
                    required_dimensions=dims,
                    store=self.store_name)

        # TODO: this is new (remove this comment)
        cube.category = self.store.category

        # TODO: required_drilldown might be a cube's attribute (fixed_dd?)
        cube.info = {
                    "required_drilldown": "date",
                    "category": cube.category
                }

        return cube

    def dimension(self, name):
        if name == "time":
            return _time_dimension

        level = Level(name, attribute_list([name]))
        dim = Dimension(name,
                         levels=[level])

        return dim

    def list_cubes(self):
        result = self.store.request(["events", "names"],
                                    {"type":"general", })
        cubes = []

        for name in result:
            label = capwords(name.replace("_", " "))
            cube = {
                    "name": name,
                    "label": label
                    }
            cubes.append(cube)

        return cubes

class MixpanelStore(Store):
    def __init__(self, api_key, api_secret, category=None):
        self.mixpanel = Mixpanel(api_key, api_secret)
        self.category = category or "Mixpanel"

    def model_provider_name(self):
        return "mixpanel"

    def request(self, *args, **kwargs):
        """Performs a mixpanel HTTP request. Raises a BackendError when
        mixpanel returns `error` in the response."""

        response = self.mixpanel.request(*args, **kwargs)

        if "error" in response:
            raise BackendError("Mixpanel request error: %s" % response["error"])

        return response
