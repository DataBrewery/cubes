"""Utility functions for computing combinations of dimensions and hierarchy levels"""

import itertools

def node_level_points(node):
    """Get all level points within given node. Node is described as tuple: (object, levels)
    where levels is a list or a tuple"""
    
    levels = []
    points = []
    for level in node[1]:
        levels.append(level)
        points.append( (node, tuple(levels)))
        
    return points

def combine_node_levels(nodes):
    """Get all possible combinations between each level from each node. It is a cartesian
    product of first node levels and all combinations of the rest of the levels"""

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
    """Create all combinations of nodes, if required_nodes are specified, make them present in each
    combination."""
    
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
    
def compute_dimension_cell_selectors(dimensions, required):
    all_nodes = []
    required_nodes = []
    
    for dim in dimensions:
        all_nodes.append( (dim, dim.levels) )
        
    for dim in required:
        required_nodes.append( (dim, dim.level_names) )
        
    combos = combine_nodes(all_nodes, required_nodes)
    
    return combos
