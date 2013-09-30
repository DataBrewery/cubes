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


_mxp_special_list = [
    {
        "name": "initial_referrer",
        "mxp_property": "$initial_referrer",
        "label": "Initial Referrer",
        "description": "The first referrer the user came from ever"
    },
    {
        "name": "initial_referring_domain",
        "mxp_property": "$initial_referring_domain",
        "label": "Initial Referring domain",
        "description": "The first referring domain the user came from ever"
    },
    {
        "name": "search_engine",
        "mxp_property": "$search_engine",
        "label": "Search Engine",
        "description": "The search engine a user came from"
    },
    {
        "name": "mp_keyword",
        "mxp_property": "mp_keyword",
        "label": "Search Keyword",
        "description": "The search keyword the user used to get to your website"
    },
    {
        "name": "os",
        "mxp_property": "$os",
        "label": "Operating System",
        "description": "The operating system of the user"
    },
    {
        "name": "browser",
        "mxp_property": "$browser",
        "label": "Browser",
        "description": "The browser of the user"
    },
    {
        "name": "referrer",
        "mxp_property": "$referrer",
        "label": "Referrer",
        "description": "The current referrer of the user"
    },
    {
        "name": "referring_domain",
        "mxp_property": "$referring_domain",
        "label": "Referring Domain",
        "description": "The current referring domain of the user"
    },
    {
        "name": "mp_country_code",
        "mxp_property": "mp_country_code",
        "label": "Country Code",
        "description": "A two letter country code representing the geolocation of the user"
    }
]

_time_dimension = create_dimension(MXP_TIME_DIM_METADATA)

_mxp_special_by_prop = dict((p["mxp_property"], p) for p in _mxp_special_list)
_mxp_special_by_name = dict((p["name"], p) for p in _mxp_special_list)

def _dimension_name(name):
    """Return a dimension name from a mixpanel property name."""
    # Try to find a special property and use prescribed name
    if name in _mxp_special_by_prop:
        fixed_name = _mxp_special_by_prop[name]["name"]
    else:
        # If there is no special property, then just replace all $ and spaces
        # with an underscore
        fixed_name = name.replace("$", "_")
        fixed_name = fixed_name.replace(" ", "_")

    return fixed_name

class MixpanelModelProvider(ModelProvider):
    def requires_store(self):
        return True

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

        dim_names = result.keys()

        options = self.cube_options(name)
        allowed_dims = options.get("allowed_dimensions", [])
        denied_dims = options.get("denied_dimensions", [])

        dim_names = []
        for dim_name in result.keys():
            if not allowed_dims and not denied_dims:
                dim_names.append(dim_name)
            elif (allowed_dims and dim_name in allowed_dims) or \
                    (denied_dims and dim_name not in denied_dims):
                dim_names.append(dim_name)

        # Replace $ with underscore _
        dims = ["time"]
        mappings = {}

        for dim_name in dim_names:
            fixed_name = _dimension_name(dim_name)
            if fixed_name != dim_name:
                mappings[fixed_name] = dim_name
            dims.append(fixed_name)

        aggregates = aggregate_list(MXP_AGGREGATES_METADATA)

        cube = Cube(name=name,
                    aggregates=aggregates,
                    linked_dimensions=dims,
                    datastore=self.store_name,
                    mappings=mappings,
                    category=self.store.category)

        self.store.logger.debug("-- cube aggs: %s" % (cube.aggregates, ))
        # TODO: required_drilldowns might be a cube's attribute (fixed_dd?)
        cube.info = {
            "required_drilldowns": ["time"]
        }

        return cube

    def dimension(self, name):
        if name == "time":
            return _time_dimension

        # Try to get a special dimension
        try:
            metadata = _mxp_special_by_name[name]
        except KeyError:
            metadata = {"name": name}

        return create_dimension(metadata)

    def list_cubes(self):
        result = self.store.request(["events", "names"], {"type": "general", })
        cubes = []

        for name in result:
            label = capwords(name.replace("_", " "))
            cube = {
                "name": name,
                "label": label,
                "category":  self.store.category
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
