import logging
import sys

__all__ = [
    "logger_name",
    "create_workspace"
]

logger_name = "cubes"
    
def _configure_logger():
    logger = logging.getLogger(logger_name)
    # logger.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s')
            # datefmt='%a, %d %b %Y %H:%M:%S',
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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

    # First try to find backend in the cubes.backends.*, so user does not
    # have to write full backend module path
    backend = sys.modules.get("cubes.backends."+backend_name)

    if not backend:
        # Then try to find a module with full module path name
        try:
            backend = sys.modules[backend_name]
        except KeyError as e:
            raise Exception("Unable to find backend module %s (%s)" % (backend_name, e))

    return backend.create_workspace(model, config)
