# -*- coding: utf-8 -*-

from __future__ import absolute_import

import os.path

from collections import OrderedDict, defaultdict

from .metadata import read_model_metadata
from .auth import NotAuthorized
from .common import read_json_file
from .errors import ConfigurationError, ArgumentError, CubesError
from .logging import get_logger
from .calendar import Calendar
from .namespace import Namespace
from .providers import find_dimension
from .localization import LocalizationContext
from .compat import ConfigParser
from . import ext
from . import compat

__all__ = [
    "Workspace",
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

def interpret_config_value(value):
    if value is None:
        return value
    if isinstance(value, compat.string_type):
        if value.lower() in ('yes', 'true', 'on'):
            return True
        elif value.lower() in ('no', 'false', 'off'):
            return False
    return value


def config_items_to_dict(items):
    return dict([ (k, interpret_config_value(v)) for (k, v) in items ])


class Workspace(object):
    def __init__(self, config=None, stores=None, load_base_model=True,
                 **_options):
        """Creates a workspace. `config` should be a `ConfigParser` or a
        path to a config file. `stores` should be a dictionary of store
        configurations, a `ConfigParser` or a path to a ``stores.ini`` file.

        Properties:

        * `stores` – dictionary of stores
        * `store_infos` – dictionary of store configurations
        * `namespace` – default namespace
        * `logger` – workspace logegr
        * `rot_dir` – root directory where all relative paths are looked for
        * `models_dir` – directory with models (if relative, then relative to
          the root directory)

        * `info` – info dictionary from the info file or info section
        * `calendar` – calendar object providing date and time functions
        * `ns_languages` – dictionary where keys are namespaces and values
          are language to translation path mappings.
        """

        # FIXME: **_options is temporary solution/workaround before we get
        # better configuration. Used internally. Don't use!

        # Expect to get ConfigParser instance
        if config is not None and not isinstance(config, ConfigParser):
            raise ConfigurationError("config should be a ConfigParser instance,"
                                     " but is %r" % (type(config),))
        
        if not config:
            # Read ./slicer.ini
            config = ConfigParser()

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
            level = config.get("workspace", "log_level").upper()
            self.logger.setLevel(level)

        # Set the default models path
        if config.has_option("workspace", "root_directory"):
            self.root_dir = config.get("workspace", "root_directory")
        elif "cubes_root" in _options:
            # FIXME: this is quick workaround, see note at the beginning of
            # this method
            self.root_dir = _options["cubes_root"]
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
                info["visualizers"] = [{
                    "label": info.get("label", info.get("name", "Default")),
                    "url": info["visualizer"]
                }]

            for key in SLICER_INFO_KEYS:
                self.info[key] = info.get(key)

        # Register stores from external stores.ini file or a dictionary
        if not stores and config.has_option("workspace", "stores_file"):
            stores = config.get("workspace", "stores_file")

            # Prepend the root directory if stores is relative
            if self.root_dir and not os.path.isabs(stores):
                stores = os.path.join(self.root_dir, stores)

        if isinstance(stores, compat.string_type):
            store_config = ConfigParser()
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
            self._register_store_dict("default", default)

        # Register [store_*] from main config (not documented)
        for section in config.sections():
            if section != "store" and section.startswith("store"):
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

        # Register Languages
        # ==================
        #

        # Register [language *]
        self.ns_languages = defaultdict(dict)
        for section in config.sections():
            if section.startswith("locale"):
                lang = section[9:]
                # namespace -> path
                for nsname, path in config.items(section):
                    if nsname == "defalt":
                        ns = self.namespace
                    else:
                        (ns, _) = self.namespace.namespace(nsname)
                    ns.add_translation(lang, path)

        # Authorizer
        # ==========

        if config.has_option("workspace", "authorization"):
            auth_type = config.get("workspace", "authorization")
            options = dict(config.items("authorization"))
            options["cubes_root"] = self.root_dir
            self.authorizer = ext.authorizer(auth_type, **options)
        else:
            self.authorizer = None

        # Configure and load models
        # =========================

        # Models are searched in:
        # [model]
        # [models] * <- depreciated!
        # TODO: add this for nicer zero-conf
        # root/model.json
        # root/main.cubesmodel
        # models/*.cubesmodel
        models = []
        # Undepreciated
        if config.has_section("model"):
            if not config.has_option("model", "path"):
                raise ConfigurationError("No model path specified")

            path = config.get("model", "path")
            models.append(("main", path))

        # TODO: Depreciate this too
        if config.has_section("models"):
            models += config.items("models")

        for model, path in models:
            self.logger.debug("Loading model %s" % model)
            self.import_model(path)

    def flush_lookup_cache(self):
        """Flushes the cube lookup cache."""
        self._cubes.clear()
        # TODO: flush also dimensions

    def _get_namespace(self, ref):
        """Returns namespace with ference `ref`"""
        if not ref or ref == "default":
            return self.namespace
        return self.namespace.namespace(ref)[0]

    def add_translation(self, locale, trans, ns="default"):
        """Add translation `trans` for `locale`. `ns` is a namespace. If no
        namespace is specified, then default (global) is used."""

        namespace = self._get_namespace(ns)
        namespace.add_translation(locale, trans)

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
        store_factory = ext.store.factory(type_)

        if hasattr(store_factory, "related_model_provider"):
            provider = store_factory.related_model_provider
        else:
            provider = None

        provider = config.pop("model_provider", provider)

        nsname = config.pop("namespace", None)

        if model:
            self.import_model(model, store=name, namespace=nsname,
                              provider=provider)
        elif provider:
            # Import empty model and register the provider
            self.import_model({}, store=name, namespace=nsname,
                              provider=provider)

        self.logger.debug("Registered store '%s'" % name)

    def _store_for_model(self, metadata):
        """Returns a store for model specified in `metadata`. """
        store_name = metadata.get("store")
        if not store_name and "info" in metadata:
            store_name = metadata["info"].get("store")

        store_name = store_name or "default"

        return store_name

    # TODO: this is very confusing process, needs simplification
    # TODO: change this to: add_model_provider(provider, info, store, languages, ns)

    def import_model(self, model=None, provider=None, store=None,
                     translations=None, namespace=None):
        """Registers the `model` in the workspace. `model` can be a
        metadata dictionary, filename, path to a model bundle directory or a
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
        # 1. Metadata
        # -----------
        # Make sure that the metadata is a dictionary
        # 
        # TODO: Use "InlineModelProvider" and "FileBasedModelProvider"

        if store and not isinstance(store, compat.string_type):
            raise ArgumentError("Store should be provided by name "
                                "(as a string).")

        # 1. Model Metadata
        # -----------------
        # Make sure that the metadata is a dictionary
        #
        # TODO: Use "InlineModelProvider" and "FileBasedModelProvider"

        if isinstance(model, compat.string_type):
            self.logger.debug("Importing model from %s. "
                              "Provider: %s Store: %s NS: %s"
                              % (model, provider, store, namespace))
            path = model
            if self.models_dir and not os.path.isabs(path):
                path = os.path.join(self.models_dir, path)
            model = read_model_metadata(path)
        elif isinstance(model, dict):
            self.logger.debug("Importing model from dictionary. "
                              "Provider: %s Store: %s NS: %s"
                              % (provider, store, namespace))
        elif model is None:
            model = {}
        else:
            raise ConfigurationError("Unknown model '%s' "
                                     "(should be a filename or a dictionary)"
                                     % model)

        # 2. Model provider
        # -----------------
        # Create a model provider if name is given. Otherwise assume that the
        # `provider` is a ModelProvider subclass instance

        if isinstance(provider, compat.string_type):
            provider = ext.model_provider(provider, model)

        # TODO: remove this, if provider is external, it should be specified
        if not provider:
            provider_name = model.get("provider", "default")
            provider = ext.model_provider(provider_name, model)

        # 3. Store
        # --------
        # Link the model with store
        store = store or model.get("store")

        if store or (hasattr(provider, "requires_store") \
                        and provider.requires_store()):
            provider.bind(self.get_store(store))

        # 4. Namespace
        # ------------

        if namespace:
            if namespace == "default":
                ns = self.namespace
            elif isinstance(namespace, compat.string_type):
                (ns, _) = self.namespace.namespace(namespace, create=True)
            else:
                ns = namespace
        elif store == "default":
            ns = self.namespace
        else:
            # Namespace with the same name as the store.
            (ns, _) = self.namespace.namespace(store, create=True)

        ns.add_provider(provider)

    def add_slicer(self, name, url, **options):
        """Register a slicer as a model and data provider."""
        self.register_store(name, "slicer", url=url, **options)
        self.import_model({}, provider="slicer", store=name)

    def cube_names(self, identity=None):
        """Return names all available cubes."""
        return [cube["name"] for cube in self.list_cubes()]

    # TODO: this is not loclized!!!
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

    def cube(self, ref, identity=None, locale=None):
        """Returns a cube with full cube namespace reference `ref` for user
        `identity` and translated to `locale`."""

        if not isinstance(ref, compat.string_type):
            raise TypeError("Reference is not a string, is %s" % type(ref))

        if self.authorizer:
            authorized = self.authorizer.authorize(identity, [ref])
            if not authorized:
                raise NotAuthorized

        # If we have a cached cube, return it
        # See also: flush lookup
        cube_key = (ref, identity, locale)
        if cube_key in self._cubes:
            return self._cubes[cube_key]

        # Find the namespace containing the cube – we will need it for linking
        # later
        (namespace, provider, basename) = self.namespace.find_cube(ref)

        cube = provider.cube(basename, locale=locale, namespace=namespace)
        cube.namespace = namespace
        cube.store = provider.store

        # TODO: cube.ref -> should be ref and cube.name should be basename
        cube.basename = basename
        cube.name = ref

        lookup = namespace.translation_lookup(locale)

        if lookup:
            # TODO: pass lookup instead of jsut first found translation
            context = LocalizationContext(lookup[0])
            trans = context.object_localization("cubes", cube.name)
            cube = cube.localized(trans)

        # Cache the cube
        self._cubes[cube_key] = cube

        return cube

    def dimension(self, name, locale=None, namespace=None, provider=None):
        """Returns a dimension with `name`. Raises `NoSuchDimensionError` when
        no model published the dimension. Raises `RequiresTemplate` error when
        model provider requires a template to be able to provide the
        dimension, but such template is not a public dimension.

        The standard lookup when linking a cube is:

        1. look in the cube's provider
        2. look in the cube's namespace – all providers within that namespace
        3. look in the default (global) namespace
        """

        return find_dimension(name, locale,
                              namespace or self.namespace,
                              provider)

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

        if isinstance(cube, compat.string_type):
            cube = self.cube(cube, identity=identity)

        locale = locale or cube.locale

        if isinstance(cube.store, compat.string_type):
            store_name = cube.store or "default"
            store = self.get_store(store_name)
            store_type = self.store_infos[store_name][0]
            store_info = self.store_infos[store_name][1]
        elif cube.store:
            store = cube.store
            store_info = store.options or {}
        else:
            store = self.get_store("default")
            store_info = store.options or {}

        store_type = store.store_type
        if not store_type:
            raise CubesError("Store %s has no store_type set" % store)

        cube_options = self._browser_options(cube)

        # TODO: merge only keys that are relevant to the browser!
        options = dict(store_info)
        options.update(cube_options)

        # TODO: Construct options for the browser from cube's options
        # dictionary and workspece default configuration

        browser_name = cube.browser
        if not browser_name and hasattr(store, "default_browser_name"):
            browser_name = store.default_browser_name
        if not browser_name:
            browser_name = store_type
        if not browser_name:
            raise ConfigurationError("No store specified for cube '%s'" % cube)

        browser = ext.browser(browser_name, cube, store=store,
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
            raise ConfigurationError("Unknown store '{}'".format(name))

        # TODO: temporary hack to pass store name and store type
        store = ext.store(type_, store_type=type_, **options)
        self.stores[name] = store
        return store
