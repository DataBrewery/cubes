"""Utility functions for computing combinations of dimensions and hierarchy
levels"""

import itertools
import logging
import sys

__all__ = [
    "logger_name",
    "get_logger",
    "create_logger",
    "IgnoringDictionary",
    "MissingPackage",
    "localize_common",
    "localize_attributes",
    "get_localizable_attributes"
]

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

class IgnoringDictionary(dict):
    """Simple dictionary extension that will ignore any keys of which values
    are empty (None/False)"""
    def setnoempty(self, key, value):
        """Set value in a dictionary if value is not null"""
        if value:
            self[key] = value

class MissingPackageError(Exception):
    """Exception raised when encountered a missing package."""
    pass
    
class MissingPackage(object):
    """Bogus class to handle missing optional packages - packages that are not
    necessarily required for Cubes, but are needed for certain features."""

    def __init__(self, package, feature = None, source = None, comment = None):
        self.package = package
        self.feature = feature
        self.source = source
        self.comment = comment

    def __call__(self, *args, **kwargs):
        self._fail()

    def __getattr__(self, name):
        self._fail()

    def _fail(self):
        if self.feature:
            use = " to be able to use: %s" % self.feature
        else:
            use = ""

        if self.source:
            source = " from %s" % self.source
        else:
            source = ""

        if self.comment:
            comment = ". %s" % self.comment
        else:
            comment = ""

        raise MissingPackageError("Optional package '%s' is not installed. "
                                  "Please install the package%s%s%s" % 
                                      (self.package, source, use, comment))

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
