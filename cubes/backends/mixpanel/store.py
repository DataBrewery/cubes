# -*- coding=utf -*-
from ...model import Cube, create_dimension
from ...model import aggregate_list
from ...browser import *
from ...stores import Store
from ...errors import *
from ...providers import ModelProvider
from ...logging import get_logger
from .mixpanel import *
from .mapper import cube_event_key
from string import capwords
import pkgutil
import time, pytz

DIMENSION_COUNT_LIMIT = 100

DEFAULT_TIME_HIERARCHY = "ymdh"

MXP_TIME_DIM_METADATA = {
    "name": "time",
    "role": "time",
    "levels": [
        { "name": "year", "label": "Year" },
        { "name": "month", "label": "Month", "info": { "aggregation_units": 3 }},
        { "name": "day", "label": "Day", "info": { "aggregation_units": 7 } },
        { "name": "hour", "label": "Hour", "info": { "aggregation_units": 6 } },
        { "name": "week", "label": "Week", "info": { "aggregation_units": 4 } },
        { "name": "date", "label": "Date", "info": { "aggregation_units": 7 } }
    ],
    "hierarchies": [
        {"name": "ymdh", "levels": ["year", "month", "day", "hour"]},
        {"name": "wdh", "levels": ["week", "date", "hour"]}
    ],
    "default_hierarchy_name": "ymdh",
    "info": {"is_date": True}
}

MXP_AGGREGATES_METADATA = [
    {
        "name": "total",
        "label": "Total"
    },
    {
        "name": "total_sma",
        "label": "Total Moving Average",
        "function": "sma",
        "measure": "total"
    },
    {
        "name": "unique",
        "label": "Unique"
    },
    {
        "name": "unique_sma",
        "label": "Unique Moving Average",
        "function": "sma",
        "measure": "unique"
    },
]


_time_dimension = create_dimension(MXP_TIME_DIM_METADATA)

def _mangle_dimension_name(name):
    """Return a dimension name from a mixpanel property name."""
    fixed_name = name.replace("$", "_")
    fixed_name = fixed_name.replace(" ", "_")

    return fixed_name

class MixpanelModelProvider(ModelProvider):
    def __init__(self, *args, **kwargs):
        super(MixpanelModelProvider, self).__init__(*args, **kwargs)

        # TODO: replace this with mixpanel mapper
        # Map properties to dimension (reverse mapping)
        self.property_to_dimension = {}
        self.event_to_cube = {}
        self.cube_to_event = {}

        mappings = self.metadata.get("mappings", {})

        # Move this into the Mixpanel Mapper
        for name in self.dimensions_metadata.keys():
            try:
                prop = mappings[name]
            except KeyError:
                pass
            else:
                self.property_to_dimension[prop] = name

        for name in self.cubes_metadata.keys():
            try:
                event = mappings[cube_event_key(name)]
            except KeyError:
                pass
            else:
                self.cube_to_event[name] = event
                self.event_to_cube[event] = name

    def default_metadata(self, metadata=None):
        """Return Mixpanel's default metadata."""

        model = pkgutil.get_data("cubes.backends.mixpanel", "mixpanel_model.json")
        metadata = json.loads(model)

        return metadata

    def requires_store(self):
        return True

    def public_dimensions(self):
        """Return an empty list. Mixpanel does not export any dimensions."""
        return []

    def cube(self, name, locale=None):
        """Creates a mixpanel cube with following variables:

        * `name` – cube name
        * `measures` – cube measures: `total` and `uniques`
        * `dimension_links` – list of linked dimension names
        * `mappings` – mapping of corrected dimension names

        Dimensions are Mixpanel's properties where ``$`` character is replaced
        by the underscore ``_`` character.
        """

        params = {
            "event": self.cube_to_event.get(name, name),
            "limit": DIMENSION_COUNT_LIMIT
        }

        result = self.store.request(["events", "properties", "top"], params)
        if not result:
            raise NoSuchCubeError("Unknown Mixpanel cube %s" % name, name)

        try:
            metadata = self.cube_metadata(name)
        except NoSuchCubeError:
            metadata = {}

        options = self.cube_options(name)
        allowed_dims = options.get("allowed_dimensions", [])
        denied_dims = options.get("denied_dimensions", [])

        dims = ["time"]
        mappings = {}

        for prop in result.keys():
            try:
                dim_name = self.property_to_dimension[prop]
            except KeyError:
                dim_name = _mangle_dimension_name(prop)

            # Skip not allowed dimensions
            if (allowed_dims and dim_name not in allowed_dims) or \
                    (denied_dims and dim_name in denied_dims):
                continue

            if dim_name != prop:
                mappings[dim_name] = prop

            dims.append(dim_name)

        aggregates = aggregate_list(MXP_AGGREGATES_METADATA)

        label = metadata.get("label", capwords(name.replace("_", " ")))
        category = metadata.get("category", self.store.category)

        cube = Cube(name=name,
                    aggregates=aggregates,
                    label=label,
                    description=category,
                    info=metadata.get("info"),
                    dimension_links=dims,
                    datastore=self.store_name,
                    mappings=mappings,
                    category=category)

        cube.info["required_drilldowns"] = ["time"]

        return cube

    def dimension(self, name, locale=None, templates=[]):
        if name == "time":
            return _time_dimension

        try:
            metadata = self.dimension_metadata(name)
        except NoSuchDimensionError:
            metadata = {"name": name}

        return create_dimension(metadata)

    def list_cubes(self):
        result = self.store.request(["events", "names"], {"type": "general", })
        cubes = []

        for event in result:
            name = self.event_to_cube.get(event, event)
            try:
                metadata = self.cube_metadata(name)
            except NoSuchCubeError:
                metadata = {}

            label = metadata.get("label", capwords(name.replace("_", " ")))
            category = metadata.get("category", self.store.category)

            cube = {
                "name": name,
                "label": label,
                "category": category
            }
            cubes.append(cube)

        return cubes


class MixpanelStore(Store):
    related_model_provider = "mixpanel"

    def __init__(self, api_key, api_secret, category=None, tz=None):
        self.mixpanel = Mixpanel(api_key, api_secret)
        self.category = category or "Mixpanel Events"
        if tz is not None:
            tz = pytz.timezone(tz)
        else:
            tz = pytz.timezone(time.strftime('%Z', time.localtime()))
        self.tz = tz
        self.logger = get_logger()

    def request(self, *args, **kwargs):
        """Performs a mixpanel HTTP request. Raises a BackendError when
        mixpanel returns `error` in the response."""

        self.logger.debug("Mixpanel request: %s" % (args,))

        try:
            response = self.mixpanel.request(*args, **kwargs)
        except MixpanelError as e:
            raise BackendError("Mixpanel request error: %s" % str(e))

        return response
