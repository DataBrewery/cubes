# -*- coding=utf -*-
import sys
from .model import load_model
from .common import get_logger
from .errors import *
import ConfigParser

__all__ = [
    "backend_aliases",
    "get_backend",
    "create_workspace",
    "create_workspace_from_config",
    "create_slicer_context",
    "Workspace"
]

backend_aliases = {
    "sql": "sql.workspace"
}

DEFAULT_BACKEND = "sql"

def get_backend(backend_name):
    """Finds the backend with name `backend_name`. First try to find backend
    relative to the cubes.backends.* then search full path. """

    backend_name = backend_aliases.get(backend_name, backend_name)
    backend = sys.modules.get("cubes.backends."+backend_name)

    if not backend:
        # Then try to find a module with full module path name
        try:
            backend = sys.modules[backend_name]
        except KeyError as e:
            raise Exception("Unable to find backend module %s (%s)" % (backend_name, e))

    if not hasattr(backend, "create_workspace"):
        raise NotImplementedError("Backend %s does not implement create_workspace" % backend_name)

    return backend

def create_slicer_context(config):
    """
    Create a context for slicer tool commands. This method is meant to be
    used not only by the slicer server, but can be reaused by any slicer
    command that requires similar context as the server. For example:
    validation of model against database, schema creation various helpers...

    Returns a dictionary with keys:

    * `model` - loaded model (with applied translations)
    * `translations` – model translations
    * `locales` - list of model locales
    * `backend_name` - backend name
    * `backend` - backend module
    * `backend_config` - backend configuration dictionary

    """

    logger = get_logger()

    context = {}

    #
    # Locales
    # 

    if config.has_section("translations"):
        context["locales"] = config.options("translations")
        context["translations"] = dict(config.items("translations"))
        logger.debug("Model translations: %s" % ", ".join(context["locales"]))
    else:
        context["locales"] = []
        context["translations"] = None

    model_path = config.get("model", "path")
    try:
        logger.debug("Loading model from %s")
        model = load_model(model_path, context["translations"])
    except Exception as e:
        if not model_path:
            model_path = 'unknown path'
        raise CubesError("Unable to load model from %s, reason: %s" % (model_path, e))

    context["model"] = model

    if model.locale:
        context["locales"].append(model.locale)
    #
    # Backend
    # 

    if config.has_option("server","backend"):
        backend_name = config.get("server","backend")
    else:
        logger.warn("no backend specified, using '%s'" % DEFAULT_BACKEND)
        backend_name = DEFAULT_BACKEND

    backend = get_backend(backend_name)

    if hasattr(backend, 'config_section'):
        logger.warn("backend %s: config_section in backend is depreciated. All backend "
                    "options are now in [workspace] section" % backend_name)
        section = backend.config_section
    else:
        section = None

    if section and section != "workspace":
        logger.warn("config section [backend] or [db] is depreciated. All backend "
                    "options are now in [workspace] section")

    context["backend_name"] = backend_name
    context["backend"] = backend

    section = section or "workspace"

    if section:
        try:
            config_dict = dict(config.items(section))
        except ConfigParser.NoSectionError:
            try:
                config_dict = dict(config.items("backend"))
                logger.warn("slicer config [backend] section is depreciated, rename to [workspace]")
            except ConfigParser.NoSectionError:
                try:
                    config_dict = dict(config.items("db"))
                    logger.warn("slicer config [db] section is depreciated, rename to [workspace]")
                except ConfigParser.NoSectionError:
                    logger.warn("no section [workspace] found in slicer config, using empty options")
                    config_dict = {}
    else:
        config_dict = {}

    context["workspace_options"] = config_dict

    return context


def create_workspace(backend_name, model, **options):
    """Designated function to create a backend-specific workspace that holds
    all relevant data and metadata for aggregated browsing.

    Use:

    >>> workspace = cubes.create_workspace("sql", model, url="postgres://localhost/database")

    Most frequently used method of workspace is browser creation:

    >>> browser = workspace.browser(cube)

    `create_workspace` finds the backend with name `backend_name` and creates
    a workspace instance. The workspace is responsible for database
    connections and for creation of aggregation browser. You can get a browser
    with method ``browser()``. The browser returned might be either created or
    reused, it depends on the backend.

    *Implementing Backend*

    The backend should provide a method `create_workspace(model, **options)`
    which returns an initialized workspace object.

    The workspace object should implement `browser(cube)`.
    """

    backend = get_backend(backend_name)

    return backend.create_workspace(model, **options)

def create_workspace_from_config(config):
    """Creates a workspace from configuration `config` which should be a
    `ConfigParser` object."""

    context = create_slicer_context(config)
    backend = context["backend"]
    workspace = backend.create_workspace(context["model"],
                                         **context["workspace_options"])

    return workspace

class Workspace(object):
    def __init__(self, model):
        """Initializes the base class for cubes workspace. Prepares all
        model's translations. Provides attributes:

        * `model`
        * `logger`

        """

        self.model = model
        if model.translations:
            self.locales = model.translations.keys()
            # Small usability treatment for debugging readability
        else:
            self.locales = []

        if model.locale:
            self.locales.append(model.locale)

        self.locales.sort()
        self.localized_models = {}
        self.logger = get_logger()

    def browser(self, cube, locale=None):
        """Creates new or provides a shared browser instance. `cube` is the
        browsed cube and `locale` is optional specification of locale to be
        used for browsing.

        Subclasses should implement this method and should ask for a model
        instance with `self.localized_model(locale)`
        """
        raise NotImplementedError("Subclasses should override browser()")

    def localized_model(self, locale):
        """Tries to translate the model. Looks for language in configuration
        file under ``[translations]``, if no translation is provided, then
        model remains untouched."""

        self.logger.debug("preparing model localization '%s' (current: '%s') "
                            "(has: %s)" % (locale, self.model.locale,
                                           self.locales))

        if not locale:
            return self.model

        if locale in self.localized_models:
            self.logger.debug("localization '%s' found" % locale)
            return self.localized_models[locale]

        elif locale == self.model.locale:
            self.localized_models[locale] = self.model
            return self.model

        else:
            model = self.model.localize(locale)

            self.localized_models[locale] = model
            return model

