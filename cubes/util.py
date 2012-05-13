"""Utility functions for computing combinations of dimensions and hierarchy
levels"""

import itertools
import sys
from .model import load_model
from .common import get_logger
import ConfigParser

__all__ = [
    "create_workspace",
    "create_slicer_context",
    "get_backend",
    "create_workspace",

    "localize_common",
    "localize_attributes",
    "get_localizable_attributes"
]

DEFAULT_BACKEND = "cubes.backends.sql.browser"

def node_level_points(node):
    """Get all level points within given node. Node is described as tuple:
    (object, levels) where levels is a list or a tuple"""
    
    levels = []
    points = []
    for level in node[1]:
        levels.append(level)
        points.append( (node, tuple(levels)))
        
    return points

def combine_node_levels(nodes):
    """Get all possible combinations between each level from each node. It is
    a cartesian product of first node levels and all combinations of the rest
    of the levels"""

    if not nodes:
        raise Exception("List of nodes is empty")
    if len(nodes) == 1:
        current_node = nodes[0]
        points = node_level_points(current_node)

        # Combos is a list of one-item lists:
        # combo = (item) => ( ( (name, (level,...)), (plevel, ...)) )
        # item = (node, plevels) => ( (name, (level,...)), (plevel, ...))
        # node = (name, levels) => (name, (level,...))
        # levels = (level)
        
        combos = []
        for point in points:
            combos.append( (point, ) )

        return combos
    else:
        current_node = nodes[0]
        current_name = current_node[0]
        other_nodes = nodes[1:]

        current_points = node_level_points(current_node) # LIST OF POINTS
        other_points = combine_node_levels(other_nodes) # LIST OF POINTS ???

        
        combos = []

        for combo in itertools.product(current_points, other_points):
            res = (combo[0], ) + combo[1]
            combos.append(res)
        
        return list(combos)

def combine_nodes(all_nodes, required_nodes = []):
    """Create all combinations of nodes, if required_nodes are specified, make
    them present in each combination."""
    
    other_nodes = []

    if not all_nodes:
        return []

    if not required_nodes:
        required_nodes = []

    for node in all_nodes:
        if node not in required_nodes:
            other_nodes.append(node)
    
    all_combinations = []

    if required_nodes:
        all_combinations += combine_node_levels(required_nodes)
    
    if other_nodes:
        for i in range(1, len(other_nodes) + 1):
            combo_nodes = itertools.combinations(other_nodes, i)
            for combo in combo_nodes:
                out = combine_node_levels(required_nodes + list(combo))
                all_combinations += out

    return all_combinations
    
# FIXME: move this to Cube as Cube.all_cuboids(requred = [])
def all_cuboids(dimensions, required = []):
    """Create cuboids for all possible combinations of dimensions for each
    levels in hierarchical order.
    
    Returns list of dimension selectors. Each dimension selector is a list of
    tuples where first element is a dimension and second element is list of
    levels. Order of selectors and also dimensions within selector is
    undefined.

    *Example 1*:

    If there are no hierarchies (dimensions are flat), then this method
    returns all combinations of all dimensions. If there are dimensions A, B,
    C with single level a, b, c, respectivelly, the output will be:
    
    Output::
    
        (A, (a)) 
        (B, (b)) 
        (C, (c)) 
        (A, (a)), (B, (b))
        (A, (a)), (C, (c))
        (B, (b)), (C, (c))
        (A, (a)), (B, (b)), (C, (c))

    *Example 2*:
    
    Take dimensions from example 1 and add requirement for dimension A (might
    be date usually). then the youtput will contain dimension A in each
    returned tuple. Tuples without dimension A will be ommited.

    Output::
    
        (A, (a)) 
        (A, (a)), (B, (b))
        (A, (a)), (C, (c))
        (A, (a)), (B, (b)), (C, (c))

    *Example 3*:
    
    If there are multiple hierarchies, then all levels are combined. Say we
    have D with d1, d2, B with b1, b2, and C with c. D (as date) is required:
    
    Output::
    
        (D, (d1))
        (D, (d1, d2))
        (D, (d1)),     (B, (b1))
        (D, (d1, d2)), (B, (b1))
        (D, (d1)),     (B, (b1, b2))
        (D, (d1, d2)), (B, (b1, b2))
        (D, (d1)),     (B, (b1)),     (C, (c))
        (D, (d1, d2)), (B, (b1)),     (C, (c))
        (D, (d1)),     (B, (b1, b2)), (C, (c))
        (D, (d1, d2)), (B, (b1, b2)), (C, (c))
        
    """
    
    all_nodes = []
    required_nodes = []
    
    for dim in required:
        if dim not in dimensions:
            raise AttributeError("Required dimension '%s' does not exist in list of computed "\
                                 "dimensions" % dim.name)
        required_nodes.append( (dim, dim.default_hierarchy.levels) )



    for dim in dimensions:
        all_nodes.append( (dim, dim.default_hierarchy.levels) )

    combos = combine_nodes(all_nodes, required_nodes)

    result = []
    for combo in combos:
        new_selector = []
        for selector in combo:
            dim = selector[0][0]
            levels = selector[1]
            new_selector.append( (dim, levels) )
        result.append(new_selector)
            
    return result

def expand_dictionary(record, separator = '.'):
    """Return expanded dictionary: treat keys are paths separated by
    `separator`, create sub-dictionaries as necessary"""

    result = {}
    for key, value in record.items():
        current = result
        path = key.split(separator)
        for part in path[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[path[-1]] = value
    return result

def localize_common(obj, trans):
    """Localize common attributes: label and description"""

    if "label" in trans:
        obj.label = trans["label"]
    if "description" in trans:
        obj.description = trans["description"]

def localize_attributes(attribs, translations):
    """Localize list of attributes. `translations` should be a dictionary with
    keys as attribute names, values are dictionaries with localizable
    attribute metadata, such as ``label`` or ``description``."""

    for (name, atrans) in translations.items():
        attrib = attribs[name]
        localize_common(attrib, atrans)

def get_localizable_attributes(obj):
    """Returns a dictionary with localizable attributes of `obj`."""

    # FIXME: use some kind of class attribute to get list of localizable attributes

    locale = {}
    try:
        if obj.label:
            locale["label"] = obj.label
    except:
        pass
            
    try:
        if obj.description:
                locale["description"] = obj.description
    except:
        pass
    return locale

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


def get_backend(backend_name):
    """Finds the backend with name `backend_name`. First try to find backend
    relative to the cubes.backends.* then search full path. """

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
