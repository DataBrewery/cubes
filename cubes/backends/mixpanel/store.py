from ...model import *
from ...browser import *
from ...stores import Store
from .mixpanel import *

DIMENSION_COUNT_LIMIT = 100

date_dimension_md = {
    "name": "date",
    "levels": ["month", "week", "day","hour"],
}

_date_dimension = create_dimension(date_dimension_md)

class MixpanelModelProvider(ModelProvider):
    def cube(self, name):
        result = self.store.request(["events", "properties", "top"],
                            {"event":name, "limit":DIMENSION_COUNT_LIMIT})
        if not result:
            raise NoSuchCubeError(name)

        dims = result.keys()
        dims.append("date")

        measures = attribute_list(["total", "uniques"])

        cube = Cube(name=name,
                    measures=measures,
                    required_dimensions=dims,
                    store=self.store_name)

        return cube

    def dimension(self, name):
        if name == "date":
            return _date_dimension

        level = Level(name, attribute_list([name]))
        dim = Dimension(name,
                         levels=[level])

        return dim

    def list_cubes(self):
        result = self.store.request(["events", "names"],
                                    {"type":"general", })
        cubes = []
        for name in result:
            cube = {
                    "name": name,
                    "label": name
                    }
            cubes.append(cube)

        return cubes

class MixpanelStore(Store):
    def __init__(self, api_key, api_secret):
        self.mixpanel = Mixpanel(api_key, api_secret)

    def model_provider_name(self):
        return "mixpanel"

    def request(self, *args, **kwargs):
        return self.mixpanel.request(*args, **kwargs)
