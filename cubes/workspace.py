# -*- coding=utf -*-
import sys
from .model import read_model_metadata, create_model_provider
from .model import Model
from .common import get_logger
from .errors import *
from .stores import open_store, create_browser
import ConfigParser

__all__ = [
    "Workspace",

    # Depreciated
    "get_backend",
    "create_workspace",
    "create_workspace_from_config",
    "create_slicer_context",
    "config_items_to_dict",
]

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
                raise Exception("Unable to load config %s. "
                                "Reason: %s" % (config, str(e)))

            config = cp
        elif not config:
            # Read ./slicer.ini
            config = ConfigParser.ConfigParser()

        self.store_infos = {}
        self.stores = {}

        self.logger = get_logger()

        self.locales = []
        self.translations = []
        self.model = None

        self._configure(config)

        # Register stores from external stores.ini file or a dictionary
        if isinstance(stores, basestring):
            store_config = ConfigParser.SafeConfigParser()
            try:
                store_config.read(stores)
            except Exception as e:
                raise Exception("Unable to read stores from %s. "
                                "Reason: %s" % (stores, str(e) ))

            for store in store_config.sections():
                self._register_store_dict(store,
                                          dict(store_config.items(store)))

        elif isinstance(stores, dict):
            for name, store in stores.items():
                self._register_store_dict(name, store)

        elif stores is not None:
            raise CubesError("Unknown stores description object: %s" %
                                                    (type(stores)))
        #
        # Model objects

        # Object ownership – model providers will be asked for the objects
        self.cube_models = {}
        self.dimension_models = {}

        # Cache of created global objects
        self._cubes = {}
        self._dimensions = {}
        # Note: providers are responsible for their own caching

    def _configure(self, config):
        """Configure the workspace from config file"""
        if config.has_option("main", "stores"):
            stores = config.get("main", "stores")

        # Register stores
        #
        # * Default store is [store] in main config file
        # * Stores are also loaded from main config file from sections with
        #   name [store_*] (not documented feature)

        if config.has_section("store"):
            self._register_store_dict("default", dict(config.items("store")))

        # Register [store_*] from main config (not documented)
        for section in config.sections():
            if section.startswith("store_"):
                name = section[6:]
                self._register_store_dict(name, dict(config.items(section)))

        if config.has_section("browser"):
            self.browser_options = dict(config.items("browser"))
        else:
            self.browser_options = {}

    def _register_store_dict(self, name, info):
        info = dict(info)
        try:
            type_ = info.pop("type")
        except KeyError:
            raise CubesError("Store '%s' has no type" % name)

        self.register_store(name, type_, **info)

    def register_store(self, name, type_, **config):
        """Adds a store configuration."""

        if name in self.store_infos:
            raise CubesError("Store %s already registered" % name)

        self.store_infos[name] = (type_, config)

    def add_model(self, model, translations=None):
        """Appends objects from `model`."""

        if isinstance(model, basestring):
            metadata = read_model_metadata(model)
            source = model
        elif isinstance(model, dict):
            metadata = model
            source = None
        else:
            raise CubesError("Unknown model source reference '%s'" % model)

        provider_name = metadata.get("provider", "default")
        provider_source = metadata.get("source", source)
        provider = create_model_provider(provider_name, provider_source, metadata)

        model_object = Model(metadata=metadata,
                             provider=provider,
                             translations=translations)

        # Get list of static or known cubes
        # "cubes" might be a list or a dictionary, depending on the provider
        for cube in metadata.get("cubes", []):
            name = _get_name(cube, "Cube")
            self._register_public_cube(name, model_object)

        # Get list of exported dimensions
        # By default all explicitly mentioned dimensions are exported.
        # 
        if "public_dimensions" in metadata:
            for dim in metadata["public_dimensions"]:
                self._register_public_dimension(dim, model_object)
        else:
            for dim in metadata.get("dimensions", []):
                name = _get_name(dim, "Dimension")
                self._register_public_dimension(name, model_object)

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

    def cube(self, name):
        """Returns a cube with `name`"""
        if name in self._cubes:
            return self._cubes[name]

        # Requirements:
        #    all dimensions in the cube should exist in the model
        #    if not they will be created

        try:
            model = self.cube_models[name]
        except KeyError:
            # TODO: give a chance to get 'unknown cube'
            # Use "dynamic_cubes" flag to determine searchable models
            # flag can be provided by provider first, then model can
            # disable it
            raise ModelError("No model providing cube '%s'" % name)

        provider = model.provider
        cube = provider.cube(name)

        self.link_cube(cube, model, provider)

        self._cubes[name] = cube
        return cube

    def link_cube(self, cube, model, provider):
        """Links dimensions to the cube in the context of `model` with help of
        `provider`."""

        # Assumption: empty cube

        # Algorithm:
        #     1. Give a chance to get the dimension from cube's provider
        #     2. If provider does not have the dimension, then use a public
        #        dimension
        #
        # Note: Provider should not raise `TemplateRequired` for public
        # dimensions
        #

        for dim_name in cube.required_dimensions:
            try:
                dim = provider.dimension(dim_name)
            except NoSuchDimensionError:
                dim = self.dimension(dim_name)
            except TemplateRequired as e:
                # FIXME: handle this special case
                raise ModelError("Template required in non-public dimension "
                                 "'%s'" % dim_name)

            cube.add_dimension(dim)

    def dimension(self, name):
        """Returns a dimension with `name`. Raises `NoSuchDimensionError` when
        no model published the dimension. Raises `RequiresTemplate` error when
        model provider requires a template to be able to provide the
        dimension, but such template is not a public dimension."""

        if name in self._dimensions:
            return self._dimensions[name]

        # Assumption: all dimensions that are to be used as templates should
        # be public dimensions. If it is a private dimension, then the
        # provider should handle the case by itself.
        missing = set( (name, ) )
        while missing:
            dimension = None
            deferred = set()

            name = missing.pop()

            # Get a model that provides the public dimension. If no model
            # advertises the dimension as public, then we fail.
            try:
                model = self.dimension_models[name]
            except KeyError:
                raise NoSuchDimensionError(name,
                                           reason="No public dimension '%s'" % name)

            try:
                dimension = model.provider.dimension(name, self._dimensions)
            except TemplateRequired as e:
                missing.add(name)
                if e.template in missing:
                    raise ModelError("Dimension templates cycle in '%s'" %
                                        e.template)
                missing.add(e.template)
                continue
            except NoSuchDimensionError:
                dimension = self._dimensions.get("name")
            else:
                # We store the newly created public dimension
                self._dimensions[name] = dimension


            if not dimension:
                raise NoSuchDimensionError(name, "Missing dimension: %s" % name)

        return dimension

    def _browser_options(self, cube):
        """Returns browser configuration options for `cube`. The options are
        taken from the configuration file and then overriden by cube's
        `browser_options` attribute."""

        options = dict(self.browser_options)
        if cube.browser_options:
            options.update(cube.browser_options)

        return options

    def browser(self, cube, locale=None):
        """Returns a browser for `cube`."""

        # TODO: bring back the localization
        # model = self.localized_model(locale)

        cube = self.cube(cube)

        store_name = cube.store or "default"
        store = self.get_store(store_name)

        options = self._browser_options(cube)

        # TODO: Construct options for the browser from cube's options dictionary and
        # workspece default configuration
        # 

        browser_name = cube.browser or store.default_browser_name
        browser = create_browser(browser_name, cube, store=store,
                                 locale=locale, **options)

        return browser

    def get_store(self, name):
        """Opens a store `name`. If the store is already open, returns the
        existing store."""

        if name in self.stores:
            return self.stores[name]

        try:
            type_, options = self.store_infos[name]
        except KeyError:
            raise CubesError("No info for store %s" % name)

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


def create_slicer_context(config):
    raise NotImplementedError("create_slicer_context() is depreciated. "
                              "Use Workspace instead." )


def create_workspace(backend_name, model, **options):
    """Depreciated. Use the following instead:

    .. code-block:: python

        ws = Workspace()
        ws.add_model(model)
        ws.register_store("default", backend_name, **options)
    """

    workspace = Workspace()
    workspace.add_model(model)
    workspace.register_store("default", backend_name, **options)
    workspace.logger.warn("create_workspace() is depreciated, "
                          "use Workspace(config) instead")
    return workspace


def create_workspace_from_config(config):
    """Depreciated. Use the following instead:

    .. code-block:: python

        ws = Workspace(config)
    """

    workspace = Workspace(config=config)
    workspace.logger.warn("create_workspace_from_config() is depreciated, "
                          "use Workspace(config) instead")
    return workspace

