import logging
import sys

from model import load_model

__all__ = [
    "logger_name",
    "get_logger",
    "create_logger",
    "create_workspace"
]

DEFAULT_BACKEND = "cubes.backends.sql.browser"

logger_name = "cubes"
logger = None

def get_logger():
    """Get brewery default logger"""
    global logger
    
    if logger:
        return logger
    else:
        return create_logger()
        
def create_logger():
    """Create a default logger"""
    global logger
    logger = logging.getLogger(logger_name)

    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s')
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

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
        backend_name = DEFAULT_BACKEND

    backend = get_backend(backend_name)
        
    if hasattr(backend, 'config_section'):
        section = backend.config_section
    else:
        section = None
    
    section = section or "backend"

    context["backend_name"] = backend_name
    context["backend"] = backend

    try:
        section = backend.config_section
    except:
        section = None
    
    section = section or "backend"

    if config.has_section(section):
        config_dict = dict(config.items(section))
    else:
        config_dict = {}

    context["backend_config"] = config_dict
    
    return context


def get_backend(backend_name):
    """Finds the backend with name `backend_name`. First try to find backend
    relative to the cubes.backends.* then search full path.
    """
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

def create_workspace(backend_name, model, **config):
    """Finds the backend with name `backend_name` and creates a workspace instance.
    The workspace is responsible for database connections and for creation of
    aggregation browser. You can get a browser with method
    ``browser_for_cube()``. The browser returned might be either created or
    reused, it depends on the backend.

    *Implementing Backend*

    The backend should be a module with variables:

    * `config_section` - name of section where backend configuration is 
      found. This is optional and if does not exist or is ``None`` then
      ``[backend]`` section is used.

    The backend should provide a method `create_workspace(model, config)`
    which returns an initialized workspace object.

    The workspace object should implement `browser_for_cube(cube)`.
    """

    backend = get_backend(backend_name)

    return backend.create_workspace(model, config)
