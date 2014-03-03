# -*-coding=utf -*-

"""Google Analytics backend for Cubes

Required packages:

    pyopenssl
    google-api-python-client

"""

from ...errors import *
from ...logging import get_logger
from ...stores import Store
from ...providers import ModelProvider
from ...model import Cube, create_dimension, aggregate_list
from .mapper import ga_id_to_identifier
import pkgutil
import json
from collections import defaultdict

from apiclient.errors import HttpError
from apiclient.discovery import build
from oauth2client.client import AccessTokenRefreshError

from collections import OrderedDict

import re

try:
    from oauth2client.client import SignedJwtAssertionCredentials
except ImportError:
    from ...common import MissingPackage
    SignedJwtAssertionCredentials = MissingPackage("oauth2client.crypt",
        "Google Analytics Backend with SignedJwtAssertionCredentials; " +
        "you may need to install pyopenssl and OpenSSL")

try:
    import httplib2
except ImportError:
    from ...common import MissingPackage
    httplib2 = MissingPackage("httplib2", "Google Analytics Backend")


# .js file that contains structure with definition of GA cubes – relation
# between metrics and dimensions that can be used together in a query
# Note: this is kind-of workaround, since GA metadata API does not provide a
# way to get this information
_GA_CUBES_JS = "https://developers.google.com/apps/js/analytics_dm/analytics_dm_js-bundle.js"

GA_TIME_DIM_METADATA = {
    "name": "time",
    "role": "time",
    "levels": [
        { "name": "year", "label": "Year" },
        { "name": "month", "label": "Month", "info": { "aggregation_units": 3 }},
        { "name": "day", "label": "Day", "info": { "aggregation_units": 7 } },
    ],
    "hierarchies": [
        {"name": "ymd", "levels": ["year", "month", "day"]},
    ],
    "default_hierarchy_name": "ymd"
}


_MEASUREMENT_TYPES = {
    'PERCENT': 'percent'
    }

def is_dimension(item):
    return item["type"] == "DIMENSION"

def is_metric(item):
    return item["type"] == "METRIC"

class GoogleAnalyticsModelProvider(ModelProvider):
    __extension_name__ = "ga"
    def __init__(self, *args, **kwargs):
        super(GoogleAnalyticsModelProvider, self).__init__(*args, **kwargs)

        self.logger = get_logger()
        self.logger.setLevel("DEBUG")

        self.ga_concepts = {};
        self.ga_measures = {};
        self.ga_dimensions = {};
        self.ga_cubes = []
        self.cube_to_group = {}
        self.group_to_cube = {}

    def requires_store(self):
        return True

    def public_dimensions(self):
        return []

    def initialize_from_store(self):
        self._refresh_metadata()

    def _measurement_type_for(self, datatype):
        return _MEASUREMENT_TYPES.get(datatype, None)

    def _refresh_metadata(self):
        """Load GA metadata. Group metrics and dimensions by `group`"""
        # TODO: move this request to the store for potential re-authentication
        rq = self.store.service.metadata().columns()
        columns = rq.list(reportType='ga').execute()

        # Note: no Cubes model related logic should be here (such as name
        # mangling)

        self.ga_metrics = OrderedDict()
        self.ga_dimensions = OrderedDict()
        self.ga_concepts = OrderedDict()
        self.ga_group_metrics = OrderedDict()

        for item in columns["items"]:
            # Get the id from the "outer" dictionary and keep juts the "inner"
            # dictionary
            item_id = item["id"]
            item = item["attributes"]
            item["id"] = item_id

            if item.get('status') == 'DEPRECATED':
                self.logger.debug("Discarding deprecated item %s" % item_id)
                continue

            if item_id.find("XX") != -1:
                self.logger.debug("Discarding template item %s (not implemented)" % item_id)
                continue

            self.ga_concepts[item_id] = item

            group = item["group"]
            if group not in self.ga_group_metrics:
                self.ga_group_metrics[group] = []

            if is_metric(item):
                self.ga_group_metrics[group].append(item)
                self.ga_metrics[item_id] = item
            elif is_dimension(item):
                self.ga_dimensions[item_id] = item
            else:
                self.logger.debug("Unknown metadata item type: %s (id: %s)"
                                  % (item["type"], item["id"]))

        self.ga_group_dims = OrderedDict()

        # TODO: enable this for dimension filtering
        # self._get_ga_cubes()

        self.cube_to_group = {}
        self.group_to_cube = {}
        self.ga_cubes = []

        for group, items in self.ga_group_metrics.items():
            dims = OrderedDict(self.ga_dimensions)

            name = re.sub("[^\w0-9_]", "_", group.lower())
            self.cube_to_group[name] = group
            self.group_to_cube[group] = name
            self.ga_cubes.append(name)

            # TODO: filter the dimensions here using _ga_cubes


            # self.ga_group_dims[group] = dims
            # metrics = set(metric["id"] for metric in items)

            # print "=== GROUP: %s" % group

            # for cube, cube_items in self.cube_concepts.items():
            #     diff = metrics - cube_items
            #     if not diff:
            #         continue

            #     if len(diff) != len(metrics):
            #         dstr = ", ".join(list(diff))
            #         print "---    incompatible metrics: %s" % (dstr, )

            self.ga_group_dims[group] = dims.values()

    def _get_ga_cubes(self):
        """Download ga cubes"""
        # Fetch cubes
        http = httplib2.Http()
        (response, content) = http.request(_GA_CUBES_JS)
        # TODO: if this fails, get locally stored copy

        # Get the _ga.cubes = {} structure from the script:
        #
        #     _ga.cubes = {
        #       ... structure data ...
        #     }
        #
        result = re.search(r"(^_ga\.cubes = )(?P<struct>{.*^}$)",
                           content, re.MULTILINE | re.DOTALL)
        groups = result.groups()
        struct = result.group("struct")

        cube_concepts = defaultdict(set)
        self.ga_cubes = []
        # Convert the quotes and parse as JSON string
        cubes = json.loads(struct.replace("'", "\""))
        for cube, concepts in cubes.items():
            self.logger.debug("GA cube: %s" % cube)
            name = re.sub("^Cube:analytics/", "", cube)
            self.ga_cubes.append(name);

            for concept_name in concepts.keys():
                try:
                    concept = self.ga_concepts[concept_name]
                except KeyError:
                    continue

                if "cubes" not in concept:
                    concept["cubes"] = set()
                concept["cubes"].add(name)

                cube_concepts[name].add(concept["id"])

        self.cube_concepts = cube_concepts

    def cube(self, name, locale=None):
        """Create a GA cube:

        * cube is a GA group
        * GA metric is cube aggregate
        * GA dimension is cube dimension
        """

        # TODO: preliminary implementation

        try:
            metadata = self.cube_metadata(name)
        except NoSuchCubeError:
            metadata = {}

        group = self.cube_to_group[name]

        # Gather aggregates

        metrics = self.ga_group_metrics[group]

        aggregates = []
        for metric in metrics:
            aggregate = {
                "name": ga_id_to_identifier(metric["id"]),
                "label": metric["uiName"],
                "description": metric.get("description")
            }
            mtype = self._measurement_type_for(metric.get('dataType'))
            if mtype:
                aggregate['info'] = { 'measurement_type':  mtype }
            aggregates.append(aggregate)

        aggregates = aggregate_list(aggregates)

        dims = self.ga_group_dims[group]
        dims = [ga_id_to_identifier(d["id"]) for d in dims]
        dims = ["time"] + dims

        cube = Cube(name=name,
                    label=metadata.get("label", group),
                    aggregates=aggregates,
                    category=metadata.get("category", self.store.category),
                    info=metadata.get("info"),
                    dimension_links=dims,
                    datastore=self.store_name)

        return cube

    def dimension(self, name, templates=[], locale=None):
        try:
            metadata = self.dimension_metadata(name)
        except NoSuchDimensionError:
            metadata = {}

        if name == "time":
            return create_dimension(GA_TIME_DIM_METADATA)

        # TODO: this should be in the mapper
        ga_id = "ga:" + name

        try:
            ga_dim = self.ga_dimensions[ga_id]
        except KeyError:
            raise NoSuchDimensionError("No GA dimension %s" % name,
                                       name=name)

        dim = {
            "name": name,
            "label": metadata.get("label", ga_dim["uiName"]),
            "description": metadata.get("description", ga_dim["description"]),
            "category": metadata.get("category", ga_dim["group"])
        }

        return create_dimension(dim)

    def list_cubes(self):
        """List GA cubes – groups of metrics and dimensions."""
        # TODO: use an option how to look at GA – what are cubes?

        cubes = []
        for cube_name in self.ga_cubes:

            try:
                metadata = self.cube_metadata(cube_name)
            except NoSuchCubeError:
                metadata = {}

            label = self.cube_to_group[cube_name]
            cube = {
                "name": cube_name,
                "label": metadata.get("label", label),
                "category": metadata.get("category", self.store.category)
            }
            cubes.append(cube)

        return cubes


class GoogleAnalyticsStore(Store):
    __extension_name__ = "ga"
    related_model_provider = "ga"

    def __init__(self, email=None, key_file=None, account_id=None,
                 account_name=None, web_property=None,
                 category=None, view_id=None, **options):

        self.logger = get_logger()

        self.service = None
        self.credentials = None
        self.category = category

        if not email:
            raise ConfigurationError("Google Analytics: email is required")
        if not key_file:
            raise ConfigurationError("Google Analytics: key_file is required")

        if account_name and account_id:
            raise ConfigurationError("Both account_name and account_id "
                                     "provided. Use only one or none.")

        with open(key_file) as f:
            self.key = f.read()

        self.email = email

        self.account_id = account_id
        self.web_property_id = web_property
        self.web_property = None
        self.profile_id = view_id
        self.profile = None

        date = options.get("default_start_date")
        if date:
            self.default_start_date = date.split("-")
        else:
            self.default_start_date = None
        date = options.get("default_start_date")
        if date:
            self.default_end_date = date.split("-")
        else:
            self.default_end_date = None

        self.credentials = SignedJwtAssertionCredentials(self.email,
                              self.key,
                              scope="https://www.googleapis.com/auth/analytics.readonly")

        # TODO: make this lazy

        self._authorize()
        self._initialize_account(account_name, account_id)

    def _authorize(self):
        self.logger.debug("Authorizing GA")
        http = httplib2.Http()
        http = self.credentials.authorize(http)
        self.service = build('analytics', 'v3', http=http)

    def _initialize_account(self, account_name, account_id):

        accounts = self.service.management().accounts().list().execute()

        self.account = None
        if account_id:
            key = "id"
            value = account_id
        elif account_name:
            key = "name"
            value = account_name
        else:
            # If no ID or account name are provided, use the first account
            self.account = accounts["items"][0]

        if not self.account:
            for account in accounts['items']:
                if account[key] == value:
                    self.account = account
                    break

        if not self.account:
            raise ConfigurationError("Unknown GA account with %s='%s'" %
                                     (key, value))

        self.account_id = self.account["id"]

        # Get the web property ID and object
        # ---

        base = self.service.management().webproperties()
        props = base.list(accountId=self.account_id).execute()
        props = props["items"]
        self.web_property = None

        if self.web_property_id:
            for p in props:
                if p["id"] == self.web_property_id:
                    self.web_property = p
                    break
        else:
            self.web_property = props[0]
            self.web_property_id = props[0]["id"]

        if not self.web_property:
            raise ConfigurationError("Unknown GA property '%s'"
                                     % self.web_property_id)
        # Get the Profile/View ID and object
        # ---

        base = self.service.management().profiles()
        profiles = base.list(accountId=self.account_id,
                           webPropertyId=self.web_property_id).execute()

        profiles = profiles["items"]

        if self.profile_id:
            for p in profiles:
                if p["id"] == self.profile_id:
                    self.profile = p
                    break
        else:
            self.profile = profiles[0]
            self.profile_id = profiles[0]["id"]

        if not self.profile:
            raise ConfigurationError("Unknown GA profile/view '%s'"
                                     % self.profile_id)

        self.timezone = self.profile["timezone"]
        self.logger.debug("GA account:%s property:%s profile:%s"
                          % (self.account_id, self.web_property_id,
                             self.profile_id))

        if not self.category:
            self.category = "GA: %s / %s" % (self.web_property["name"],
                                           self.profile["name"])

    def get_data(self, **kwargs):
        # Documentation:
        # https://google-api-client-libraries.appspot.com/documentation/analytics/v3/python/latest/analytics_v3.data.ga.html
        ga = self.service.data().ga()

        try:
            response = ga.get(ids='ga:%s' % self.profile_id,
                              **kwargs).execute()
        except TypeError as e:
            raise ArgumentError("Google Analytics Error: %s"
                                % str(e))
        except HttpError as e:
            raise BrowserError("Google Analytics HTTP Error: %s"
                                % str(e))
        except AccessTokenRefreshError as e:
            raise NotImplementedError("Re-authorization not implemented yet")

        return response
