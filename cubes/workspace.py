import sys
from .model import load_model
from .common import get_logger
import ConfigParser

__all__ = [
    "backend_aliases",
    "get_backend",
    "create_workspace",
    "create_slicer_context"
]

backend_aliases = {
    "sql": "sql.star"
}

DEFAULT_BACKEND = "sql.browser"

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

    * `model` - loaded model
    * `locales` - list of model locales
    * `backend_name` - backend name
    * `backend` - backend module
    * `backend_config` - backend configuration dictionary
    """

    logger = get_logger()

    context = {}

    model_path = config.get("model", "path")
    try:
        model = load_model(model_path)
    except Exception as e:
        if not model_path:
            model_path = 'unknown path'
        raise Exception("Unable to load model from %s, reason: %s" % (model_path, e))

    context["model"] = model

    #
    # Locales
    # 

    if config.has_option("model", "locales"):
        context["locales"] = config.get("model", "locales").split(",")
    elif model.locale:
        context["locales"] = [model.locale]
    else:
        context["locales"] = []

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
    """Finds the backend with name `backend_name` and creates a workspace
    instance. The workspace is responsible for database connections and for
    creation of aggregation browser. You can get a browser with method
    ``browser()``. The browser returned might be either created or reused, it
    depends on the backend.

    *Implementing Backend*

    The backend should provide a method `create_workspace(model, **options)`
    which returns an initialized workspace object.

    The workspace object should implement `browser(cube)`.
    """

    backend = get_backend(backend_name)

    return backend.create_workspace(model, **options)
