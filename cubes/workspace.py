# -*- coding: utf-8 -*-

import sys
from .metadata import read_model_metadata
from .auth import NotAuthorized
from .model import Model
from .common import read_json_file
from .logging import get_logger
from .errors import *
from .calendar import Calendar
from .extensions import extensions
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
        cube_names = set()
        for provider in self.providers:
            cubes = provider.list_cubes()
            # Cehck for duplicity
            for cube in cubes:
                name = cube["name"]
                if name in cube_names:
                    raise ModelError("Duplicate cube '%s'" % name)
                cube_names.add(name)

            all_cubes += cubes

        if recursive:
            for name, ns in self.namespaces.items():
                cubes = ns.list_cubes(recursive=True)
                for cube in cubes:
                    cube["name"] = "%s.%s" % (name, cube["name"])
                all_cubes += cubes

        return all_cubes

    def cube(self, name, locale=None, recursive=False):
        """Return cube named `name`.

        If `recursive` is ``True`` then look for cube in child namespaces.
        """
        cube = None

        for provider in self.providers:
            # TODO: use locale
            try:
                cube = provider.cube(name)
            except NoSuchCubeError:
                pass
            else:
                cube.provider = provider
                return cube

        if recursive:
            for key, namespace in self.namespaces.items():
                try:
                    cube = namespace.cube(name, locale, recursive=True)
                except NoSuchCubeError:
                    # Just continue with sibling
                    pass
                else:
                    return cube

        raise NoSuchCubeError("Unknown cube '%s'" % str(name), name)

    def dimension(self, name, locale=None, templates=None):
        dim = None

        # TODO: cache dimensions
        for provider in self.providers:
            # TODO: use locale
            try:
                dim = provider.dimension(name, locale=locale,
                                         templates=templates)
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
    def __init__(self, config=None, stores=None, load_base_model=True):
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

        # Logging
        # =======
        #Log to file or console
        if config.has_option("workspace", "log"):
            self.logger = get_logger(path=config.get("workspace", "log"))
        else:
            self.logger = get_logger()

        #Change to log level if necessary
        if config.has_option("workspace", "log_level"):
            self.logger.setLevel(config.get("workspace", "log_level").upper())


        # Set the default models path
        if config.has_option("workspace", "root_directory"):
            self.root_dir = config.get("workspace", "root_directory")
        else:
            self.root_dir = ""

        if config.has_option("workspace", "models_directory"):
            self.models_dir = config.get("workspace", "models_directory")
        elif config.has_option("workspace", "models_path"):
            self.models_dir = config.get("workspace", "models_path")
        else:
            self.models_dir = ""

        if self.root_dir and not os.path.isabs(self.models_dir):
            self.models_dir = os.path.join(self.root_dir, self.models_dir)

        if self.models_dir:
            self.logger.debug("Models root: %s" % self.models_dir)
        else:
            self.logger.debug("Models root set to current directory")

        # Namespaces and Model Objects
        # ============================

        self.namespace = Namespace()

        # Cache of created global objects
        self._cubes = {}
        # Note: providers are responsible for their own caching

        if config.has_option("workspace", "lookup_method"):
            method = config.get("workspace", "lookup_method")
            if method not in ["exact", "recursive"]:
                raise ConfigurationError("Unknown namespace lookup method '%s'"
                                         % method)
            self.lookup_method = method
        else:
            # TODO: make this "global"
            self.lookup_method = "recursive"

        # Info
        # ====

        self.info = OrderedDict()

        if config.has_option("workspace", "info_file"):
            path = config.get("workspace", "info_file")

            if self.root_dir and not os.path.isabs(path):
                path = os.path.join(self.root_dir, path)

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

        # Register stores from external stores.ini file or a dictionary
        if not stores and config.has_option("workspace", "stores_file"):
            stores = config.get("workspace", "stores_file")

            # Prepend the root directory if stores is relative
            if self.root_dir and not os.path.isabs(stores):
                stores = os.path.join(self.root_dir, stores)

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

        # Register Stores
        # ===============
        #
        # * Default store is [store] in main config file
        # * Stores are also loaded from main config file from sections with
        #   name [store_*] (not documented feature)

        default = None
        if config.has_section("store"):
            default = dict(config.items("store"))

        if default:
            self._register_store_dict("default",default)

        # Register [store_*] from main config (not documented)
        for section in config.sections():
            if section.startswith("store_"):
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
        # ==========

        if config.has_option("workspace", "authorization"):
            auth_type = config.get("workspace", "authorization")
            options = dict(config.items("authorization"))
            self.authorizer = extensions.authorizer(auth_type, **options)
        else:
            self.authorizer = None

        # Configure and load models
        # =========================

        # Load base model (default)
        import pkgutil
        if config.has_option("workspace", "load_base_model"):
            load_base = config.getboolean("workspace", "load_base_model")
        else:
            load_base = load_base_model

        if load_base:
            loader = pkgutil.get_loader("cubes")
            path = os.path.join(loader.filename, "models/base.cubesmodel")
            self.import_model(path)

        # TODO: remove this depreciation code
        if config.has_section("model"):
            self.logger.warn("Section [model] is depreciated. Use 'model' in "
                             "[workspace] for single default model or use "
                             "section [models] to list multiple models.")
            if config.has_option("model", "path"):
                source = config.get("model", "path")
                self.logger.debug("Loading model from %s" % source)
                self.import_model(source)

        models = []
        if config.has_option("workspace", "model"):
            models.append(config.get("workspace", "model"))
        if config.has_section("models"):
            models += [path for name, path in config.items("models")]

        for model in models:
            self.logger.debug("Loading model %s" % model)
            self.import_model(model)

    def _register_store_dict(self, name, info):
        info = dict(info)
        try:
            type_ = info.pop("type")
        except KeyError:
            try:
                type_ = info.pop("backend")
            except KeyError:
                raise ConfigurationError("Store '%s' has no type specified" % name)
            else:
                self.logger.warn("'backend' is depreciated, use 'type' for "
                                 "store (in %s)." % str(name))

        self.register_store(name, type_, **info)

    def register_default_store(self, type_, **config):
        """Convenience function for registering the default store. For more
        information see `register_store()`"""
        self.register_store("default", type_, **config)

    def register_store(self, name, type_, include_model=True, **config):
        """Adds a store configuration."""

        config = dict(config)

        if name in self.store_infos:
            raise ConfigurationError("Store %s already registered" % name)

        self.store_infos[name] = (type_, config)

        # Model and provider
        # ------------------

        # If store brings a model, then include it...
        if include_model and "model" in config:
            model = config.pop("model")
        else:
            model = None

        # Get related model provider or override it with configuration
        ext = extensions.store.get(type_)
        provider = ext.related_model_provider
        provider = config.pop("model_provider", provider)

        nsname = config.pop("namespace", None)

        if model:
            self.import_model(model, store=name, namespace=nsname,
                              provider=provider)
        elif provider:
            # Import empty model and register the provider
            self.import_model({}, store=name, namespace=nsname,
                              provider=provider)

    def _store_for_model(self, metadata):
        """Returns a store for model specified in `metadata`. """
        store_name = metadata.get("store")
        if not store_name and "info" in metadata:
            store_name = metadata["info"].get("store")

        store_name = store_name or "default"

        return store_name

    # TODO: This is new method, replaces add_model. "import" is more
    # appropriate as it denotes that objects are imported and the model is
    # "dissolved"
    def import_model(self, metadata=None, provider=None, store=None,
                     translations=None, namespace=None):

        """Registers the model `metadata` in the workspace. `metadata` can be
        a metadata dictionary, filename, path to a model bundle directory or a
        URL.

        If `namespace` is specified, then the model's objects are stored in 
        the namespace of that name.

        `store` is an optional name of data store associated with the model.
        If not specified, then the one from the metadata dictionary will be
        used.

        Model's provider is registered together with loaded metadata. By
        default the objects are registered in default global namespace.

        Note: No actual cubes or dimensions are created at the time of calling
        this method. The creation is deferred until
        :meth:`cubes.Workspace.cube` or :meth:`cubes.Workspace.dimension` is
        called.
        """

        if isinstance(metadata, basestring):
            self.logger.debug("Importing model from %s. "
                              "Provider: %s Store: %s NS: %s"
                              % (metadata, provider, store, namespace))
            path = metadata
            if self.models_dir and not os.path.isabs(path):
                path = os.path.join(self.models_dir, path)
            metadata = read_model_metadata(path)
        elif isinstance(metadata, dict):
            self.logger.debug("Importing model from dictionary. "
                              "Provider: %s Store: %s NS: %s"
                              % (provider, store, namespace))

        else:
            raise ConfigurationError("Unknown model '%s' "
                                     "(should be a filename or a dictionary)"
                                     % model)

        # Create a model provider if name is given. Otherwise assume that the
        # `provider` is a ModelProvider subclass instance
        # TODO: add translations
        if isinstance(provider, basestring):
            provider = extensions.model_provider(provider, metadata)

        if not provider:
            provider_name = metadata.get("provider", "default")
            provider = extensions.model_provider(provider_name, metadata)

        store = store or metadata.get("store")

        if store or provider.requires_store():
            if store and not isinstance(store, basestring):
                raise ArgumentError("Store should be a name, not an object")
            provider.set_store(self.get_store(store), store)

        # We are not getting list of cubes here, we are lazy

        if namespace:
            if isinstance(namespace, basestring):
                (ns, _) = self.namespace.namespace(namespace, create=True)
            else:
                ns = namepsace
        elif store != "default":
            # Store in store's namespace
            # TODO: use default namespace
            (ns, _) = self.namespace.namespace(store, create=True)
        else:
            ns = self.namespace

        ns.add_provider(provider)

    # TODO: depreciated
    def add_model(self, model, name=None, store=None, translations=None):
        self.logger.warn("add_model() is depreciated, use import_model()")
        return self.import_model(model, store=store, translations=translations)

    def add_slicer(self, name, url, **options):
        """Register a slicer as a model and data provider."""
        self.register_store(name, "slicer", url=url, **options)

        model = {
            "store": name,
            "provider": "slicer",
            "store": name
        }
        self.import_model(model)

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

        cube_key = (name, locale)
        if name in self._cubes:
            return self._cubes[cube_key]

        (ns, ns_cube) = self.namespace.namespace_for_cube(name)

        recursive = (self.lookup_method == "recursive")
        cube = ns.cube(ns_cube, locale=locale, recursive=recursive)

        # Set cube name to the full cube reference that includes namespace as
        # well
        cube.name = name
        cube.basename = name.split(".")[-1]

        self.link_cube(cube, ns)

        self._cubes[cube_key] = cube

        return cube

    def link_cube(self, cube, namespace):
        """Links dimensions to the cube in the context of `model` with help of
        `provider`."""

        # Assumption: empty cube

        if cube.provider:
            providers = [cube.provider]
        else:
            providers = []
        if namespace:
            providers.append(namespace)

        # Add the default namespace as the last look-up place, if not present
        providers.append(self.namespace)

        dimensions = {}
        for link in cube.dimension_links:
            dim_name = link["name"]
            try:
                dim = self.dimension(dim_name,
                                     locale=cube.locale,
                                     providers=providers)
            except TemplateRequired as e:
                raise ModelError("Dimension template '%s' missing" % dim_name)

            dimensions[dim_name] = dim

        cube.link_dimensions(dimensions)

    def _lookup_dimension(self, name, providers, templates):
        """Look-up a dimension `name` in chain of `providers` which might
        include a mix of providers and namespaces.

        `templates` is an optional dictionary with already instantiated
        dimensions that can be used as templates.
        """

        dimension = None
        required_template = None

        # FIXME: cube's provider might be hit at least twice: once as provider,
        # second time as part of cube's namespace

        for provider in providers:
            try:
                dimension = provider.dimension(name, templates=templates)
            except NoSuchDimensionError:
                pass
            else:
                return dimension
            # We are passing the TemplateRequired exception
        raise NoSuchDimensionError("Dimension '%s' not found" % name,
                                   name=name)

    def dimension(self, name, locale=None, providers=None):
        """Returns a dimension with `name`. Raises `NoSuchDimensionError` when
        no model published the dimension. Raises `RequiresTemplate` error when
        model provider requires a template to be able to provide the
        dimension, but such template is not a public dimension.

        The standard lookup is:

        1. look in the cube's provider
        2. look in the cube's namespace (all providers)
        3. look in the default (global) namespace
        """

        # Collected dimensions – to be used as templates
        templates = {}

        if providers:
            providers = list(providers)
        else:
            # If no providers are given then use the default namespace
            # (otherwise we would end up without any dimension)
            providers = [self.namespace]

        # Assumption: all dimensions that are to be used as templates should
        # be public dimensions. If it is a private dimension, then the
        # provider should handle the case by itself.
        missing = set( (name, ) )
        while missing:
            dimension = None
            deferred = set()

            name = missing.pop()

            # First give a chance to provider, then to namespace
            dimension = None
            required_template = None

            try:
                dimension = self._lookup_dimension(name, providers, templates)
            except TemplateRequired as e:
                required_template = e.template

            if required_template in templates:
                raise BackendError("Some model provider didn't make use of "
                                   "dimension template '%s' for '%s'"
                                   % (required_template, name))

            if required_template:
                missing.add(name)
                if required_template in missing:
                    raise ModelError("Dimension templates cycle in '%s'" %
                                     required_template)
                missing.add(required_template)

            # Store the created dimension to be used as template
            if dimension:
                templates[name] = dimension

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

        locale = locale or cube.locale

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

        browser = extensions.browser(browser_name, cube, store=store,
                                     locale=locale, calendar=self.calendar,
                                     **options)

        # TODO: remove this once calendar is used in all backends
        browser.calendar = self.calendar

        return browser

    def cube_features(self, cube, identity=None):
        """Returns browser features for `cube`"""
        # TODO: this might be expensive, make it a bit cheaper
        # recycle the feature-providing browser or something. Maybe use class
        # method for that
        return self.browser(cube, identity).features()

    def get_store(self, name=None):
        """Opens a store `name`. If the store is already open, returns the
        existing store."""

        name = name or "default"

        if name in self.stores:
            return self.stores[name]

        try:
            type_, options = self.store_infos[name]
        except KeyError:
            raise ConfigurationError("No info for store %s" % name)

        store = extensions.store(type_, **options)
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

