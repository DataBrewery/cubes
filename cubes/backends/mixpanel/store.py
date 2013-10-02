# -*- coding=utf -*-
from ...model import Cube, create_dimension
from ...model import aggregate_list
from ...browser import *
from ...stores import Store
from ...errors import *
from ...providers import ModelProvider
from .mixpanel import *
from string import capwords
from cubes.common import get_logger
import pkgutil

DIMENSION_COUNT_LIMIT = 100

DEFAULT_TIME_HIERARCHY = "ymdh"

MXP_TIME_DIM_METADATA = {
    "name": "time",
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

        # Map properties to dimension (reverse mapping)
        self.property_to_dimension = {}
        mappings = self.metadata.get("mappings", {})
        for dim_name in self.dimensions_metadata.keys():
            try:
                prop = mappings[dim_name]
            except KeyError:
                pass
            else:
                self.property_to_dimension[prop] = dim_name

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

    def cube(self, name):
        """Creates a mixpanel cube with following variables:

        * `name` – cube name
        * `measures` – cube measures: `total` and `uniques`
        * `linked_dimensions` – list of linked dimension names
        * `mappings` – mapping of corrected dimension names

        Dimensions are Mixpanel's properties where ``$`` character is replaced
        by the underscore ``_`` character.
        """

        result = self.store.request(["events", "properties", "top"],
                                    {"event": name,
                                     "limit": DIMENSION_COUNT_LIMIT})
        if not result:
            raise NoSuchCubeError(name)

        try:
            metadata = self.cube_metadata(name)
        except ModelError:
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
                    linked_dimensions=dims,
                    datastore=self.store_name,
                    mappings=mappings,
                    category=category)

        # TODO: required_drilldowns might be a cube's attribute (fixed_dd?)
        cube.info = {
            "required_drilldowns": ["time"]
        }

        return cube

    def dimension(self, name):
        if name == "time":
            return _time_dimension

        try:
            metadata = self.dimension_metadata(name)
        except KeyError:
            metadata = {"name": name}

        return create_dimension(metadata)

    def list_cubes(self):
        result = self.store.request(["events", "names"], {"type": "general", })
        cubes = []

        for name in result:
            try:
                metadata = self.cube_metadata(name)
            except ModelError:
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
    def __init__(self, api_key, api_secret, category=None):
        self.mixpanel = Mixpanel(api_key, api_secret)
        self.category = category or "Mixpanel Events"
        self.logger = get_logger()

    def request(self, *args, **kwargs):
        """Performs a mixpanel HTTP request. Raises a BackendError when
        mixpanel returns `error` in the response."""

        self.logger.debug("Mixpanel request: %s" % (args,))

        response = self.mixpanel.request(*args, **kwargs)

        if "error" in response:
            raise BackendError("Mixpanel request error: %s" % response["error"])

        return response
