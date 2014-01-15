# -*- coding=utf -*-
import sys
from .providers import read_model_metadata, create_model_provider
from .auth import create_authorizer, NotAuthorized
from .model import Model
from .common import read_json_file
from .logging import get_logger
from .errors import *
from .stores import open_store, create_browser
from .calendar import Calendar
import os.path
import ConfigParser
from collections import OrderedDict

__all__ = [
    "Workspace",

    # Depreciated
    "get_backend",
    "create_workspace",
    "create_workspace_from_config",
    "config_items_to_dict",
]


SLICER_INFO_KEYS = (
    "name",
    "label",
    "description",  # Workspace model description
    "copyright",    # Copyright for the data
    "license",      # Data license
    "maintainer",   # Name (and maybe contact) of data maintainer
    "contributors", # List of contributors
    "visualizers",  # List of dicts with url and label of server's visualizers
    "keywords",     # List of keywords describing server's cubes
    "related"       # List of dicts with related servers
)


def config_items_to_dict(items):
    return dict([ (k, interpret_config_value(v)) for (k, v) in items ])


def interpret_config_value(value):
    if value is None:
        return value
    if isinstance(value, basestring):
        if value.lower() in ('yes', 'true', 'on'):
            return True
        elif value.lower() in ('no', 'false', 'off'):
            return False
    return value


def _get_name(obj, object_type="Object"):
    if isinstance(obj, basestring):
        name = obj
    else:
        try:
            name = obj["name"]
        except KeyError:
            raise ModelError("%s has no name" % object_type)

    return name

class Namespace(object):
    def __init__(self):
        self.namespaces = {}
        self.providers = []
        self.objects = {}

    def namespace(self, path, create=False):
        """Returns a tuple (`namespace`, `remainder`) where `namespace` is
        the deepest namespace in the namespace hierarchy and `remainder` is
        the remaining part of the path that has no namespace (is an object
        name or contains part of external namespace).

        If path is empty or not provided then returns self.
        """

        if not path:
            return (self, [])

        if isinstance(path, basestring):
            path = path.split(".")

        namespace = self
        found = False
        for i, element in enumerate(path):
            remainder = path[i+1:]
            if element in namespace.namespaces:
                namespace = namespace.namespaces[element]
                found = True
            else:
                remainder = path[i:]
                break

        if not create:
            return (namespace, remainder)
        else:
            for element in remainder:
                namespace = namespace.create_namespace(element)

            return (namespace, [])

    def create_namespace(self, name):
        """Create a namespace `name` in the receiver."""
        namespace = Namespace()
        self.namespaces[name] = namespace
        return namespace

    def namespace_for_cube(self, cube):
        """Returns a tuple (`namespace`, `relative_cube`) where `namespace` is
        a namespace conaining `cube` and `relative_cube` is a name of the
        `cube` within the `namespace`. For example: if cube is
        ``slicer.nested.cube`` and there is namespace ``slicer`` then that
        namespace is returned and the `relative_cube` will be ``nested.cube``"""

        cube = str(cube)
        split = cube.split(".")
        if len(split) > 1:
            path = split[0:-1]
            cube = split[-1]
        else:
            path = []
            cube = cube

        (namespace, remainder) = self.namespace(path)

        if remainder:
            relative_cube = "%s.%s" % (".".join(remainder), cube)
        else:
            relative_cube = cube

        return (namespace, relative_cube)

    def list_cubes(self, recursive=False):
        """Retursn a list of cube info dictionaries with keys: `name`,
        `label`, `description`, `category` and `info`."""

        all_cubes = []
        for provider in self.providers:
            # TODO: check for cube uniqueness
            all_cubes += provider.list_cubes()

        if recursive:
            for name, ns in self.namespaces.items():
                cubes = ns.list_cubes(recursive=True)
                for cube in cubes:
                    cube.name = "%s.%s" % (name, cube["name"])
                all_cubes += cubes

        return all_cubes

    def cube(self, name, locale=None):
        """Return cube named `name`"""
        cube = None

        for provider in self.providers:
            # TODO: use locale
            try:
                cube = provider.cube(name)
            except NoSuchCubeError:
                pass
            else:
                return cube

        raise NoSuchCubeError("Unknown cube '%s'" % str(name), name)

    def dimension(self, name, locale=None, templates=None):
        dim = None

        for provider in self.providers:
            # TODO: use locale
            try:
                dim = provider.dimension(name, templates)
            except NoSuchDimensionError:
                pass
            else:
                return dim

        raise NoSuchDimensionError("Unknown dimension '%s'" % str(name), name)

    def add_provider(self, provider):
        self.providers.append(provider)


class ModelObjectInfo(object):
    def __init__(self, name, scope, metadata, provider, model_metadata,
                  locale, translations):
        self.name = name
        self.scope = scope
        self.metadata = metadata
        self.provider = provider
        self.model_metadata = model_metadata
        self.locale = locale
        self.translations = translations
        self.master = None
        self.instances = {}

    def add_instance(self, instance, locale=None, identity=None):
        key = (locale, identity)
        self.instances[key] = instance

    def instance(self, locale=None, identity=None):
        key = (locale, identity)
        return self.instances[key]


class Workspace(object):
    def __init__(self, config=None, stores=None):
        """Creates a workspace. `config` should be a `ConfigParser` or a
        path to a config file. `stores` should be a dictionary of store
        configurations, a `ConfigParser` or a path to a ``stores.ini`` file.
        """
        if isinstance(config, basestring):
            cp = ConfigParser.SafeConfigParser()
            try:
                cp.read(config)
            except Exception as e:
                raise ConfigurationError("Unable to load config %s. "
                                "Reason: %s" % (config, str(e)))

            config = cp

        elif not config:
            # Read ./slicer.ini
            config = ConfigParser.ConfigParser()

        self.store_infos = {}
        self.stores = {}

        self.logger = get_logger()

        self.namespace = Namespace()
        self.default_namespace_name = None

        if config.has_option("workspace", "log"):
            formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s')
            handler = logging.FileHandler(config.get("workspace", "log"))
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        if config.has_option("workspace", "log_level"):
            self.logger.setLevel(config.get("workspace", "log_level").upper())

        self.locales = []
        self.translations = []

        self.info = OrderedDict()

        if config.has_option("workspace", "default_namespace"):
            name = config.get("workspace", "default_namespace")
            if name == "default":
                self.default_namespace_name = None
            else:
                self.default_namespace_name = name

        if config.has_option("workspace", "info"):
            path = config.get("workspace", "info_file")
            info = read_json_file(path, "Slicer info")
            for key in SLICER_INFO_KEYS:
                self.info[key] = info.get(key)
        elif config.has_section("info"):
            info = dict(config.items("info"))
            if "visualizer" in info:
                info["visualizers"] = [ {"label": info.get("label",
                                                info.get("name", "Default")),
                                         "url": info["visualizer"]} ]
            for key in SLICER_INFO_KEYS:
                self.info[key] = info.get(key)

        #
        # Model objects
        self._models = []

        # Object ownership – model providers will be asked for the objects
        self.cube_models = {}
        self.dimension_models = {}

        # Cache of created global objects
        self._cubes = {}
        self._dimensions = {}
        # Note: providers are responsible for their own caching

        # Register stores from external stores.ini file or a dictionary
        if isinstance(stores, basestring):
            store_config = ConfigParser.SafeConfigParser()
            try:
                store_config.read(stores)
            except Exception as e:
                raise ConfigurationError("Unable to read stores from %s. "
                                "Reason: %s" % (stores, str(e) ))

            for store in store_config.sections():
                self._register_store_dict(store,
                                          dict(store_config.items(store)))

        elif isinstance(stores, dict):
            for name, store in stores.items():
                self._register_store_dict(name, store)

        elif stores is not None:
            raise ConfigurationError("Unknown stores description object: %s" %
                                                    (type(stores)))

        # Calendar
        # ========

        if config.has_option("workspace", "timezone"):
            timezone = config.get("workspace", "timezone")
        else:
            timezone = None

        if config.has_option("workspace", "first_weekday"):
            first_weekday = config.get("workspace", "first_weekday")
        else:
            first_weekday = 0

        self.logger.debug("Workspace calendar timezone: %s first week day: %s"
                          % (timezone, first_weekday))
        self.calendar = Calendar(timezone=timezone,
                                 first_weekday=first_weekday)

        # Register stores
        #
        # * Default store is [datastore] in main config file
        # * Stores are also loaded from main config file from sections with
        #   name [store_*] (not documented feature)

        default = None
        if config.has_section("datastore"):
            default = dict(config.items("datastore"))
        elif config.has_section("workspace"):
            self.logger.warn("No [datastore] configuration found, using old "
                             "backend & [workspace]. Update you config file.")
            default = {}
            default = dict(config.items("workspace"))
            default["type"] = config.get("server", "backend") if config.has_option("server", "backend") else None

            if not default.get("type"):
                self.logger.warn("No store type specified, assuming 'sql'")
                default["type"] = "sql"

        if default:
            self._register_store_dict("default",default)

        # Register [store_*] from main config (not documented)
        for section in config.sections():
            if section.startswith("datastore_"):
                name = section[10:]
                self._register_store_dict(name, dict(config.items(section)))
            elif section.startswith("store_"):
                name = section[6:]
                self._register_store_dict(name, dict(config.items(section)))

        if config.has_section("browser"):
            self.browser_options = dict(config.items("browser"))
        else:
            self.browser_options = {}

        if config.has_section("main"):
            self.options = dict(config.items("main"))
        else:
            self.options = {}

        # Authorizer
        if config.has_option("workspace", "authorization"):
            auth_type = config.get("workspace", "authorization")
            options = dict(config.items("authorization"))
            self.authorizer = create_authorizer(auth_type, **options)
        else:
            self.authorizer = None

        # Load models

        if config.has_section("model"):
            self.logger.warn("Section [model] is depreciated. Use 'model' in "
                             "[workspace] for single default model or use "
                             "section [models] to list multiple models.")
            if config.has_option("model", "path"):
                source = config.get("model", "path")
                self.logger.debug("Loading model from %s" % source)
                self.add_model(source)

        if config.has_option("workspace", "models_path"):
            models_path = config.get("workspace", "models_path")
        else:
            models_path = None

        models = []
        if config.has_option("workspace", "model"):
            models.append(config.get("workspace", "model"))
        if config.has_section("models"):
            models += [path for name, path in config.items("models")]

        self._load_models(models_path, models)

    def _load_models(self, root, paths):
        """Load `models` with root path `models_path`."""

        if root:
            self.logger.debug("Models root: %s" % root)
        else:
            self.logger.debug("Models root set to current directory")

        for path in paths:
            self.logger.debug("Loading model %s" % path)
            if root and not os.path.isabs(path):
                path = os.path.join(root, path)
            self.add_model(path)

    def _register_store_dict(self, name, info):
        info = dict(info)
        try:
            type_ = info.pop("type")
        except KeyError:
            try:
                type_ = info.pop("backend")
            except KeyError:
                raise ConfigurationError("Datastore '%s' has no type specified" % name)
            else:
                self.logger.warn("'backend' is depreciated, use 'type' for "
                                 "datastore (in %s)." % str(name))

        self.register_store(name, type_, **info)

    def register_default_store(self, type_, **config):
        """Convenience function for registering the default store. For more
        information see `register_store()`"""
        self.register_store("default", type_, **config)

    def default_namespace(self):
        # TODO: this fails when default name is "store"
        if not self.default_namespace_name:
            ns = self.namespace
        else:
            (ns, _) = self.namespace.namespace(self.default_namespace_name,
                                             create=True)
        return ns

    def register_store(self, name, type_, include_model=True, **config):
        """Adds a store configuration."""

        if name in self.store_infos:
            raise ConfigurationError("Store %s already registered" % name)

        self.store_infos[name] = (type_, config)

        if include_model and "model" in config:
            model = config["model"]
            if self.default_namespace_name == "store":
                nsname = config.get("namespace")
            else:
                nsname = self.default_namespace_name

            if nsname == "default":
                nsname = None

            self.import_model(model, store=name, namespace=namespace)

    def _store_for_model(self, metadata):
        """Returns a store for model specified in `metadata`. """
        store_name = metadata.get("datastore")
        if not store_name and "info" in metadata:
            store_name = metadata["info"].get("datastore")

        store_name = store_name or "default"

        return store_name

    # TODO: This is new method, replaces add_model. "import" is more
    # appropriate as it denotes that objects are imported and the model is
    # "dissolved"
    def import_model(self, metadata=None, provider=None, store=None,
                     translations=None, namespace=None):

        if isinstance(metadata, basestring):
            metadata = read_model_metadata(metadata)
        elif not isinstance(metadata, dict):
            raise ConfigurationError("Unknown model '%s' "
                                     "(should be a filename or a dictionary)"
                                     % model)

        # Create a model provider if name is given. Otherwise assume that the
        # `provider` is a ModelProvider subclass instance
        # TODO: add translations
        if isinstance(provider, basestring):
            provider = create_model_provider(provider, metadata)

        if not provider:
            provider_name = metadata.get("provider", "default")
            provider = create_model_provider(provider_name, metadata)

        if provider.requires_store():
            if not isinstance(store, basestring):
                raise ArgumentError("Store should be a name, not an object")

            store_name = store
            store = self.get_store(store_name)

            provider.set_store(store, store_name)

        # We are not getting list of cubes here, we are lazy

        if namespace:
            if isinstance(namespace, basestring):
                (ns, _) = self.namespace.namespace(namespace, create=True)
            else:
                ns = namepsace
        else:
            ns = self.namespace

        ns.add_provider(provider)

    # TODO: depreciated
    def add_model(self, model, name=None, store=None, translations=None):
        """Registers the `model` in the workspace. `model` can be a metadata
        dictionary, filename, path to a model bundle directory or a URL.

        If `name` is specified, then it is used instead of name in the
        model. `store` is an optional name of data store associated with the
        model.

        Model is added to the list of workspace models. Model provider is
        determined and associated with the model. Provider is then asked to
        list public cubes and public dimensions which are registered in the
        workspace.

        No actual cubes or dimensions are created at the time of calling this
        method. The creation is deffered until :meth:`cubes.Workspace.cube` or
        :meth:`cubes.Workspace.dimension` is called.

        """

        # self.logger.warn("add_model() is depreciated, use import_model()")
        return self.import_model(model, store=store, translations=translations)

    def _register_public_dimension(self, name, model):
        if name in self.dimension_models:
            model_name = model.name or "(unknown)"
            previous_name = self.dimension_models[name].name or "(unknown)"

            raise ModelError("Duplicate public dimension '%s' in model %s, "
                             "previous model: %s" %
                                        (name, model_name, previous_name))

        self.dimension_models[name] = model

    def _register_public_cube(self, name, model):
        if name in self.cube_models:
            model_name = model.name or "(unknown)"
            previous_name = self.cube_models[name].name or "(unknown)"

            raise ModelError("Duplicate public cube '%s' in model %s, "
                             "previous model: %s" %
                                        (name, model_name, previous_name))

        self.cube_models[name] = model

    def add_slicer(self, name, url, **options):
        """Register a slicer as a model and data provider."""
        self.register_store(name, "slicer", url=url, **options)

        model = {
            "store": name,
            "provider": "slicer",
            "datastore": name
        }
        self.add_model(model)

    def list_cubes(self, identity=None):
        """Get a list of metadata for cubes in the workspace. Result is a list
        of dictionaries with keys: `name`, `label`, `category`, `info`.

        The list is fetched from the model providers on the call of this
        method.

        If the workspace has an authorizer, then it is used to authorize the
        cubes for `identity` and only authorized list of cubes is returned.
        """

        all_cubes = self.namespace.list_cubes(recursive=True)

        if self.authorizer:
            by_name = dict((cube["name"], cube) for cube in all_cubes)
            names = [cube["name"] for cube in all_cubes]

            authorized = self.authorizer.authorize(identity, names)
            all_cubes = [by_name[name] for name in authorized]

        return all_cubes

    def cube(self, name, identity=None, locale=None):
        """Returns a cube with `name`"""

        if not isinstance(name, basestring):
            raise TypeError("Name is not a string, is %s" % type(name))


        if self.authorizer:
            authorized = self.authorizer.authorize(identity, [name])
            if not authorized:
                raise NotAuthorized

        cube_key = (name, identity, locale)
        if name in self._cubes:
            return self._cubes[cube_key]

        (ns, ns_cube) = self.namespace.namespace_for_cube(name)

        cube = ns.cube(ns_cube)

        # Set cube name to the full cube reference that includes namespace as
        # well
        cube.name = name

        if not cube:
            raise NoSuchCubeError(name, "No cube '%s' returned from "
                                     "provider." % name)

        self.link_cube(cube, ns)

        self._cubes[cube_key] = cube

        return cube

    def _model_for_cube(self, name):
        """Discovers the first model that can provide cube with `name`"""

        # Note: this will go through all model providers and gets a list of
        # provider's cubes. Might be a bit slow, if the providers get the
        # models remotely.

        model = None
        for model in self._models:
            cubes = model.provider.list_cubes()
            names = [cube["name"] for cube in cubes]
            if name in names:
                break

        if not model:
            raise ModelError("No model for cube '%s'" % name)

        return model

    def link_cube(self, cube, namespace):
        """Links dimensions to the cube in the context of `model` with help of
        `provider`."""

        # Assumption: empty cube

        for dim_name in cube.linked_dimensions:
            try:
                dim = self.dimension(dim_name, namespace)
            except TemplateRequired as e:
                # FIXME: handle this special case
                raise ModelError("Template required in private dimension "
                                 "'%s'" % dim_name)

            cube.add_dimension(dim)

    def dimension(self, name, namespace=None):
        """Returns a dimension with `name`. Raises `NoSuchDimensionError` when
        no model published the dimension. Raises `RequiresTemplate` error when
        model provider requires a template to be able to provide the
        dimension, but such template is not a public dimension.
        """

        # Return a public dimension if no provider for private dimensions is
        # specified.
        if not namespace and name in self._dimensions:
            return self._dimensions[name]

        # Create a copy of public dimension list
        dimensions = dict(self._dimensions)

        namespace = namespace or self.namespace

        # Assumption: all dimensions that are to be used as templates should
        # be public dimensions. If it is a private dimension, then the
        # provider should handle the case by itself.
        missing = set( (name, ) )
        while missing:
            dimension = None
            deferred = set()

            name = missing.pop()

            # First give a chance to provider
            dimension = None

            # Required template name
            required_template = None

            try:
                dimension = namespace.dimension(name, templates=dimensions)
            except NoSuchDimensionError:
                dimension = None
            except TemplateRequired as e:
                dimension = None
                required_template = e.template

            if not dimension and name in self._dimensions:
                # Get cached dimension
                dimension = self._dimensions[name]

            # Now we try to look-up public dimension
            if not dimension and not required_template:
                if namespace == self.namespace:
                    raise NoSuchDimensionError("No public dimension '%s'" % name)

                # Get dimension from "default" (global) namespace
                try:
                    dimension = self.namespace.dimension(name,
                                                         templates=dimensions)
                except TemplateRequired as e:
                    required_template = e.template
                except NoSuchDimensionError:
                    raise InternalError("No global dimension '%s'" % name)
                else:
                    # Register the public dimension
                    self._dimensions[name] = dimension

            if required_template:
                missing.add(name)
                if required_template in missing:
                    raise ModelError("Dimension templates cycle in '%s'" %
                                     required_template)
                missing.add(required_template)
                continue

            if not dimension:
                raise NoSuchDimensionError("Missing dimension: %s" % name, name)

            # We store the newly created public dimension
            dimensions[name] = dimension

        return dimension

    def _browser_options(self, cube):
        """Returns browser configuration options for `cube`. The options are
        taken from the configuration file and then overriden by cube's
        `browser_options` attribute."""

        options = dict(self.browser_options)
        if cube.browser_options:
            options.update(cube.browser_options)

        return options

    def browser(self, cube, locale=None, identity=None):
        """Returns a browser for `cube`."""

        # TODO: bring back the localization
        # model = self.localized_model(locale)

        if isinstance(cube, basestring):
            cube = self.cube(cube, identity=identity)

        # TODO: check if the cube is "our" cube

        store_name = cube.datastore or "default"
        store = self.get_store(store_name)
        store_type = self.store_infos[store_name][0]
        store_info = self.store_infos[store_name][1]

        cube_options = self._browser_options(cube)

        # TODO: merge only keys that are relevant to the browser!
        options = dict(store_info)
        options.update(cube_options)

        # TODO: Construct options for the browser from cube's options dictionary and
        # workspece default configuration
        #

        browser_name = cube.browser
        if not browser_name and hasattr(store, "default_browser_name"):
            browser_name = store.default_browser_name
        if not browser_name:
            browser_name = store_type
        if not browser_name:
            raise ConfigurationError("No store specified for cube '%s'" % cube)

        browser = create_browser(browser_name, cube, store=store,
                                 locale=locale, **options)

        browser.calendar = self.calendar

        return browser

    def cube_features(self, cube, identity=None):
        """Returns browser features for `cube`"""
        # TODO: this might be expensive, make it a bit cheaper
        # recycle the feature-providing browser or something. Maybe use class
        # method for that
        return self.browser(cube, identity).features()

    def get_store(self, name="default"):
        """Opens a store `name`. If the store is already open, returns the
        existing store."""

        if name in self.stores:
            return self.stores[name]

        try:
            type_, options = self.store_infos[name]
        except KeyError:
            raise ConfigurationError("No info for store %s" % name)

        store = open_store(type_, **options)
        self.stores[name] = store
        return store

    def close(self):
        """Closes the workspace with all open stores and other associated
        resources."""

        for store in self.open_stores:
            store.close()


# TODO: Remove following depreciated functions

def get_backend(name):
    raise NotImplementedError("get_backend() is depreciated. "
                              "Use Workspace instead." )


def create_workspace(backend_name, model, **options):
    raise NotImplemented("create_workspace() is depreciated, "
                         "use Workspace(config) instead")


def create_workspace_from_config(config):
    raise NotImplemented("create_workspace_from_config() is depreciated, "
                         "use Workspace(config) instead")

