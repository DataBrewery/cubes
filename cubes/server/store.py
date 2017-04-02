# -*- coding=utf -*-
from ..metadata import *
from ..query import *
from ..stores import Store
from ..errors import *
from ..logging import get_logger
from ..settings import Setting, SettingType
import json

from urllib.request import urlopen, build_opener
from urllib.request import HTTPPasswordMgrWithDefaultRealm
from urllib.request import HTTPBasicAuthHandler
from urllib.parse import urlencode

DEFAULT_SLICER_URL = "http://localhost:5000"

class _default_opener:
    def __init__(self):
        pass

    def open(self, url, *args, **kwargs):
        return urlopen(url, *args, **kwargs)

class SlicerStore(Store, name="slicer"):
    related_model_provider = "slicer"

    extension_desc = """
    Uses external Slicer as a store. Aggregation is performed on the remote
    server and results are relayed.
    """
    extension_settings = [
        Setting(
            name= "url",
            desc= "URL of slicer server to connect to",
            type= SettingType.str,
        ),
        Setting(
            name= "authentication",
            desc= "Authentication method (pass_parameter or none)",
            type= SettingType.str,
        ),
        Setting(
            name= "auth_identity",
            desc= "Authenticated identity (user name, key, ...)",
            type= SettingType.str,
        ),
        Setting(
            name= "auth_parameter",
            desc= "Name of authentication URL parameter " \
                           "(default: api_key",
            type= SettingType.str,
        ),
        Setting(
            name= "username",
            desc= "HTTP authentication username",
            type= SettingType.str,
        ),
        Setting(
            name= "password",
            desc= "HTTP authentication password",
            type= SettingType.str,
        ),
    ]

    def __init__(self, url=None, authentication=None,
                 auth_identity=None, auth_parameter=None,
                 **options):

        super(SlicerStore, self).__init__(**options)

        url = url or DEFAULT_SLICER_URL

        self.url = url
        self.logger = get_logger()

        if authentication and authentication not in ["pass_parameter", "none"]:
            raise ConfigurationError("Unsupported authentication method '%s'"
                                     % authentication)

        self.authentication = authentication
        self.auth_identity = auth_identity
        self.auth_parameter = auth_parameter or "api_key"

        if "username" in options and "password" in options:
            # make a basic auth-enabled opener
            _pmgr = HTTPPasswordMgrWithDefaultRealm()
            _pmgr.add_password(None, self.url, options['username'], options['password'])
            self.opener = build_opener(HTTPBasicAuthHandler(_pmgr))
            self.logger.info("Created slicer opener using basic auth credentials with username %s", options['username'])
        else:
            self.opener = _default_opener()

        # TODO: cube prefix
        # TODO: model mappings as in mixpanel

    def request(self, action, params=None, is_lines=False):
        """
        * `action` – server action (path)
        # `params` – request parameters
        """

        params = dict(params) if params else {}

        if self.authentication == "pass_parameter":
            params[self.auth_parameter] = self.auth_identity

        params_str = urlencode(params)
        request_url = '%s/%s' % (self.url, action)

        if params_str:
            request_url += '?' + params_str

        self.logger.debug("slicer request: %s" % (request_url, ))
        response = self.opener.open(request_url)

        if response.getcode() == 404:
            raise MissingObjectError
        elif response.getcode() != 200:
            raise BackendError("Slicer request error (%s): %s"
                               % (response.getcode(), response.read()))

        if is_lines:
            return _JSONLinesIterator(response)
        else:
            try:
                result = json.loads(response.read())
            except:
                result = {}

            return result

    def cube_request(self, action, cube, params=None, is_lines=False):
        action = "cube/%s/%s" % (cube, action)
        return self.request(action, params, is_lines)


class _JSONLinesIterator(object):
    def __init__(self, stream):
        self.stream = stream

    def __iter__(self):
        for line in self.stream:
            yield json.loads(line)


class SlicerModelProvider(ModelProvider, name="slicer"):
    """
    Uses external Slicer server as a model provider.
    """

    def requires_store(self):
        return True

    def list_cubes(self):
        return self.store.request('cubes')

    def cube(self, name, locale=None):
        params = {}
        if locale:
            params["lang"] = locale
        try:
            cube_desc = self.store.cube_request("model", name, params)
        except MissingObjectError:
            raise NoSuchCubeError("Unknown cube '%s'" % name, name)

        # create_cube() expects dimensions to be a list of names and linked
        # later, the Slicer returns whole dimension descriptions

        dimensions = cube_desc.pop("dimensions")
        features = cube_desc.pop("features")

        if features:
            # Note: if there are "features" in the browser options, they are
            # eaten here. Is this ok? They should not be there as they should
            # have been processed by the original browser/workspace.
            browser_options = cube_desc.pop("browser_options", {})
            browser_options["features"] = features
            cube_desc["browser_options"] = browser_options

        # Link the cube in-place
        cube = create_cube(cube_desc)
        for dim in dimensions:
            dim = create_dimension(dim)
            cube.add_dimension(dim)

        cube.store = self.store
        return cube

    def dimension(self, name, locale=None, tempaltes=None):
        raise NoSuchDimensionError(name)
