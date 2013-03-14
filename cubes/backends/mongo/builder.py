import cubes.common
import cubes.browser
import base

import itertools
import logging

import types

try:
    import pymongo
    import bson
except ImportError:
    pass


class MongoSimpleCubeBuilder(object):
    """Construct preaggregated cube.
    """
    def __init__(self, cube, database, 
                    fact_collection, 
                    cube_collection = None,
                    measures = None,
                    aggregate_flag_field = "_is_aggregate",
                    required_dimensions = ["date"]):
        """Creates simple cube builder in mongo. See :meth:`MongoSimpleCubeBuilder.compute` for more 
        information about computation algorithm
        
        :Attributes:
            * `cube` - description of a cube from logical model
            * `fact_collection` - either name or mongo collection containing facts (should correspond)
              to `cube` definition
            * `cube_collection` - name or mongo collection where computed cell aggregates will be
              stored. By default it is the same collection as fact collection. Make sure to properely
              set `aggregate_flag_field`.
            * `measures` - list of attributes that are going to be aggregated. By default it is
              ``[amount]``
            * `aggregate_flag_field` - name of field (key) that distincts fact fields from aggregated
              records. Should be used when fact collection and cube collection is the same. By default
              it is ``_is_aggregate``.
            * `required_dimensions` - dimensions that are required for all cells. By default: 
              ``[date]``
        """
                    
        self.cube = cube
        self.database = database
        self.aggregate_flag_field = aggregate_flag_field

        self.fact_collection = fact_collection
        if cube_collection:
            self.cube_collection = cube_collection
        else:
            self.cube_collection = fact_collection
            
        if type(self.fact_collection) in (types.StringType, types.UnicodeType):
            print 'MONGOFICATION OF FACT'
            self.fact_collection = self.database[self.fact_collection]

        if type(self.cube_collection) in (types.StringType, types.UnicodeType):
            print 'MONGOFICATION OF FACT'
            self.cube_collection = self.database[self.cube_collection]
            
        if required_dimensions:
            dims = []
            for dim in required_dimensions:
                dims.append(self.cube.dimension(dim))

        self.required_dimensions = dims
        self.measure_agg = None
        self.selectors = None
        
        if measures == None:
            measures = ["amount"]
            
        self.measures = measures
        
        self.log = logging.getLogger(cubes.logger_name)
        
        self.cell_record_name = "_selector"
        self.cell_reference_record_name = "_cell"
        
    def compute(self):
        """Compute a multidimensional cube. Computed aggregations for cells can be stored either
        in separate collection or in the same source - fact collection. Attribute `aggregate_flag_field`
        is used to distinct between facts and aggregated cells.
        
        Algorithm:
        
        #. Compute all dimension combinations (for all levels if there are any hierarchies). Each
           combination is called `selector` and is represented by a list of tuples: (dimension, levels).
           For more information see: :meth:`cubes.common.compute_dimension_cell_selectors`.

        #. Compute aggregations for each point within dimension selector. Use MongoDB group function
           (alternative to map-reduce).
        
        #. Each record for aggregated cell is stored in target collection (see above).

        This is naive non-optimized method of cube computation: no aggregations are reused for
        computation.
        """

        self.log.info("Computing cube %s" % self.cube.name)

        self.cube_collection.remove({self.aggregate_flag_field: True})

        selectors = compute_dimension_cell_selectors(self.cube.dimensions,
                                                     self.required_dimensions)

        self.log.info("got %d dimension level selectors ", len(selectors))

        for selector in selectors:
            self.compute_cell(selector)

        self.cube_collection.ensure_index(self.cell_record_name)
                                                                
    def compute_cell(self, selector):
        """ 
        Compute aggregation for cell specified by selector. cell is computed using MongoDB
        aggregate_ function. Computed records are inserted into `cube_collection` and they contain:
        
        * key fields used for grouping
        * aggregated measures suffixed with `_sum`, for example: `amount_sum`
        * record count in `record_count`
        * cell selector as `_selector` (configurable) with dimension names as keys and current
          dimension levels as values, for example: {"date": ["year", "month"] }
        * cell reference as `_cell` (configurable) with dimension names as keys and level 
          keys forming dimension paths as values, for example: {"date": [2010, 10] }

        .. _aggregate: http://www.mongodb.org/display/DOCS/Aggregation#Aggregation-Group

        :Arguments:
            * `selector` is a list of tuples: (dimension, level_names)
                    
        .. note::
        
            Only 'sum' aggregation is being computed. Other aggregations might be implemented in the
            future, such as average, min, max, rank, ...
        """
        self.log.info("computing selector")

        key_maps = []
        attrib_maps = []
        selector_record = {}
        
        for dimsel in selector:
            dim = dimsel[0]
            levels = dimsel[1]
            self.log.info("-- dimension: %s levels: %s", dim.name, levels)

            level_names = []
            for level in levels:
                level_names.append(level.name)
                mapped = base.dimension_field_mapping(self.cube, dim, level.key)
                key_maps.append(mapped)
                
                for field in level.attributes:
                    mapped = base.dimension_field_mapping(self.cube, dim, field)
                    attrib_maps.append((mapped[0], field))

            selector_record[dim.name] = level_names
            

        ###########################################
        # Prepare group command parameters
        #
        # condition - filter condition for find() (check for existence of keys)
        # keys - list of keys to be used for grouping
        # measures - list of measures

        condition = {}
        keys = []
        for mapping in key_maps:
            mapped_key = mapping[0]
            if isinstance(mapped_key, cubes.model.Attribute):
                mapped_key = mapped_key.full_name()
            condition[mapped_key] = { "$exists" : True}
            keys.append(mapped_key)

        fields = []
        for mapping in attrib_maps:
            mapped = mapping[0]
            if isinstance(mapped, cubes.model.Attribute):
                mapped = mapped.full_name()
            fields.append(mapped)
        
        for measure in self.measures:
            mapping = base.fact_field_mapping(self.cube, measure)
            fields.append(mapping[0])
            
        self.log.info("condition: %s", condition)
        self.log.info("keys: %s", keys)
        self.log.info("fields: %s", fields)

        # Exclude aggregates:
        condition[self.aggregate_flag_field] = {'$ne': True}

        ####################################################
        # Prepare group functions + reduce + finalize
        #

        initial = { "record_count": 0 }

        aggregate_lines = []
        for measure in self.measures:
            measure_agg_name = measure + "_sum"
            line = "out.%s += doc.%s;" % (measure_agg_name, measure)
            aggregate_lines.append(line)
            initial[measure_agg_name] = 0

        reduce_function = '''
        function(doc, out) {
                out.record_count ++;
                %(aggregate_lines)s
                return out;
        }\n''' % {"aggregate_lines": "\n".join(aggregate_lines)}

        finalize_function = None

        k = keys[0].to_dict().keys()

        print 'key', k
        print 'condition', condition
        print 'initial', initial
        print 'reduce_function', reduce_function
        print 'finalize', finalize_function

        cursor = self.fact_collection.group(key = k, condition = condition,
                                            initial = initial, reduce = reduce_function,
                                            finalize = finalize_function)

        for record in cursor:
            # use: cubes.commons.expand_dictionary(record)
            cell = {}
            for dimsel in selector:
                dimension, levels = dimsel
                path = []
                for level in levels:
                    mapped = base.dimension_field_mapping(self.cube, dimension, level.key)
                    path.append(record[mapped[0]])
                cell[dimension.name] = path

            record = self.construct_record(record)
            record[self.aggregate_flag_field] = True
            record[self.cell_record_name] = selector_record
            record[self.cell_reference_record_name] = cell
            self.cube_collection.insert(record)

    def construct_record(self, record):
        result = {}
        for key, value in record.items():
            current = result
            path = key.split(".")
            for part in path[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[path[-1]] = value
        return result


def compute_dimension_cell_selectors(dimensions, required = []):
    """Create selector for all possible combinations of dimensions for each levels in hierarchical
    order.

    Returns list of dimension selectors. Each dimension selector is a list of tuples where first element
    is a dimension and second element is list of levels. Order of selectors and also dimensions within
    selector is undefined.

    *Example 1*:

    If there are no hierarchies (dimensions are flat), then this method returns all combinations of all
    dimensions. If there are dimensions A, B, C with single level a, b, c, respectivelly, the output
    will be:

    Output::

        (A, (a))
        (B, (b))
        (C, (c))
        (A, (a)), (B, (b))
        (A, (a)), (C, (c))
        (B, (b)), (C, (c))
        (A, (a)), (B, (b)), (C, (c))

    *Example 2*:

    Take dimensions from example 1 and add requirement for dimension A (might be date usually). then
    the youtput will contain dimension A in each returned tuple. Tuples without dimension A will
    be ommited.

    Output::

        (A, (a))
        (A, (a)), (B, (b))
        (A, (a)), (C, (c))
        (A, (a)), (B, (b)), (C, (c))

    *Example 3*:

    If there are multiple hierarchies, then all levels are combined. Say we have D with d1, d2, B with
    b1, b2, and C with c. D (as date) is required:

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
        return list(combos)
