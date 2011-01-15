import aggregation_browser
import itertools

try:
    import pymongo
    import bson
except ImportError:
    pass

def level_points(dimension):
    level_points = []
    levels = []
    for level in dimension.levels:
        levels.append(level)
        level_points.append( (dimension, list(levels)) )
        
    return level_points

def combine(dimensions):
    if not dimensions:
        return []
    else:
        head = dimensions[0]
        tail = dimensions[1:]
        
        head_points = level_points(head)
        tail_combine = combine(dimensions)
    


def create_combined_dimension_points1(dimensions, required_dimensions = None):
    """Compute list of dimension points through all dimensions and all dimension levels.
    
    :Parameters:
        * `dimensions`: dimensions to compute
        * `required_dimensiosn`: dimensions that should be present in all points
        
    Note: Currently only default hierarchy will be used. Hierarchy selection will be available
    in the future.
    
    Returs: list of tuples (dimension, level_list), for example::

        [(dim1, (l1)), (dim2, (l1))],
        [(dim1, (l1, l2)), (dim2, (l1))],
        [(dim1, (l1)), (dim2, (l1, l2))],
    
    """
    print("--> Generating combinations for %d dimensions" % len(dimensions))
    print("--- required: %s" % required_dimensions)
    
    dim_points = {}
    for dim in dimensions:
        levels = []
        for level in dim.levels:
            levels.append(level)
            if not dim in dim_points:
                dim_points[dim] = []
            dim_points[dim].append(list(levels))

    print("--- Level points:")
    for dim, llist in dim_points.items():
        for levels in llist:
            print "--- dim: %s levels: %s" % (dim.name, levels)
            

    # Create all combinations of dimensions
    require_test = lambda d: d in required_dimensions
    combined_dims = []
    for i in range(1, len(dimensions)):
        combos = itertools.combinations(dimensions, i)
        for combo in combos:
            # Include only required dimensions
            # for item in combo:
            
            detected = itertools.takewhile(require_test, combo)
            if len(list(detected)):
                combined_dims.append(combo)
    
    # Create all combinations of dimensions and their levels

    # require_test = lambda d: d in required_dimensions
    combined_points = []
    # for i in range(1, len(dimensions)):
    #     combos = itertools.combinations(points, i)
    #     # print "COMBOS: %d %s" % (len(list(combs)), list(combs))
    #     for combo in combos:
    #         # Include only required dimensions
    #         print "NEXT COMBO %s" % ([[e[0].name, e[1]] for e in combo])
    #         # for item in combo:
    #         detected = itertools.takewhile(require_test, combo)
    #         if len(list(detected)):
    #             combined_points.append(combo)
    return combined_points


class MongoAggregationBrowser(aggregation_browser.AggregationBrowser):
    """MongoDB Aggregation Browser"""
        
    def __init__(self, cube, collection):
        """Create mongoDB Aggregation Browser
        """
        super(MongoAggregationBrowser, self).__init__(cube)
        self.collection = collection
    
    def aggregate(self, cuboid, measure):
        pass

class MongoCubeGenerator(object):
    def __init__(self, cube, database, 
                    fact_collection, 
                    cube_collection,
                    measure = "amount",
                    required_dimensions = ["date"]):
        self.cube = cube
        self.database = database
        self.fact_collection = fact_collection
        self.cube_collection = cube_collection
        self.required_dimensions = required_dimensions
        self.measure_agg = None
        self.combined_points = None

        self.measure = measure
    
    def compute(self):
        """Brute-force cube computation - no reuse of precomputed aggregates"""

        print("--> Computing cube %s" % self.cube.name)

        print("--> creating point combinations")
        self.create_combined_points()

        print("--> truncating cube")
        self.database[self.cube_collection].remove()

        self.measure_agg = self.measure + "_sum"

        print("--> preparing reduce function")

        parameters = { 
                       "measure_agg": self.measure_agg,
                       "measure": self.measure }
        
        self.reduce_function = '''
        function(key, vals) {
            var ret = {%(measure_agg)s:0, record_count:1};
            for(var i = 0; i < vals.length; i++) {
                ret.%(measure_agg)s += vals[i].%(measure_agg)s;
                ret.record_count += vals[i].record_count;
            }
            return ret;
        }\n''' % parameters

        print("--> computing points")
        for point in self.combined_points:
            self.compute_point(point)
            
    def compute_point(self, point):
        print "--- point:"

        ################################################################
        # 1. Create map function
        all_keys, emit_str = self.emit_for_point(point)
        map_function = 'function() { %s }' % emit_str
        
        ################################################################
        # 2. Create filtering query
        #
        # This step is requred - prevents failure on records where
        # key field does not exit

        query = {}
        for key in all_keys:
            query[key] = { "$exists" : "true" }

        ################################################################
        # 3. Run map-reduce
        
        print "--> Running map-reduce"
        print "--- MAP: \n%s\n" % (map_function)
        result = self.database.command("mapreduce", self.fact_collection,
                                            map = map_function,
                                            reduce = self.reduce_function,
                                            query = query,
                                            out = { "merge" : self.cube_collection })
    
    def emit_for_point1(self, point):
        groupers = []
        all_keys = []
        for dimpoint in point:
            dim = dimpoint[0]
            print "---     dim: %s" % dim.name
            mapped_keys = []
            for level_name in dimpoint[1]:
                print "---     level: %s" % level_name
                level = dim.level(level_name)
                mapped_key = self.cube.dimension_field_mapping(dim, level.key)
                mapped_keys.append(mapped_key[0])
            
            all_keys.extend(mapped_keys)

            mapped_keys = ["this." + key for key in mapped_keys]
            
            string = ", ".join(mapped_keys)
            grouper = "%s: [%s]" % (dim.name, string)
            groupers.append(grouper)
    

        # FIXME: allow more aggregations and aggregation types

        groupers_str = ", ".join(groupers)
        attributes_str = "boo:1"
        parameters = { "groupers": groupers_str, 
                       "measure_agg": self.measure_agg,
                       "measure": self.measure,
                       "attributes": attributes_str }

        emit_str = '''
            emit(
                {%(groupers)s},
                {%(measure_agg)s: this.%(measure)s, record_count:1, attributes: {%(attributes)s}}
            );
        ''' % parameters
    
        return (all_keys, emit_str)

    def emit_for_point(self, point):
        groupers = []
        all_keys = []
        
        print "--- KEYS"
        # Collect keys
        for dimpoint in point:
            dim = dimpoint[0]
            print "---     dim: %s" % dim.name
            mapped_keys = []
            for level_name in dimpoint[1]:
                print "---     level: %s" % level_name
                level = dim.level(level_name)
                mapped_key = self.cube.dimension_field_mapping(dim, level.key)
                mapped_keys.append(mapped_key[0])

            all_keys.extend(mapped_keys)

            mapped_keys = ["this." + key for key in mapped_keys]

            string = ", ".join(mapped_keys)
            grouper = "%s: [%s]" % (dim.name, string)
            groupers.append(grouper)


        # Collect attributes

        print "--- ATTRIBUTES"
        decorators = []
        for dimpoint in point:
            dim = dimpoint[0]
            print "---     dim: %s" % dim.name
            attributes = []
            for level_name in dimpoint[1]:
                print "---     level: %s" % level_name
                level = dim.level(level_name)
                for field in level.attributes:
                    mapped = self.cube.dimension_field_mapping(dim, field)
                    attributes.append((mapped[0], field))

            # attributes.extend(mapped_keys)

            attributes = ["%s: this.%s" % (logical, physical) for physical, logical in attributes]

            string = ", ".join(attributes)
            decorator = "%s: {%s}" % (dim.name, string)
            decorators.append(decorator)

        print "DECOR: %s" % decorators
        # FIXME: allow more aggregations and aggregation types

        groupers_str = ", ".join(groupers)
        decorators_str = ", ".join(decorators)
        attributes_str = "boo:1"
        parameters = { "groupers": groupers_str, 
                       "measure_agg": self.measure_agg,
                       "measure": self.measure,
                       "attributes": decorators_str }

        emit_str = '''
            emit(
                {cut : {%(groupers)s}, attributes: {%(attributes)s}},
                {%(measure_agg)s: this.%(measure)s, record_count:1}
            );
        ''' % parameters

        return (all_keys, emit_str)
        
    def create_combined_points(self):
        dimensions = self.cube.dimensions
        points = []
        for dim in dimensions:
            levels = []
            for level in dim.levels:
                levels.append(level)
                points.append((dim, list(levels)))

        print("--> Generating combinations for %d dimensions" % len(dimensions))
        require_test = lambda d: d[0].name in self.required_dimensions
        self.combined_points = []
        for i in range(1, len(dimensions)):
            combs = itertools.combinations(points, i)
            for comb in combs:
                # Include only required dimensions
                detected = itertools.takewhile(require_test, comb)
                if len(list(detected)):
                    self.combined_points.append(comb)
                    
class MongoSimpleCubeBuilder(object):
    """docstring for ClassName"""
    def __init__(self, cube, database, 
                    fact_collection, 
                    cube_collection,
                    measure = "amount",
                    aggregate_flag_field = "is_aggregate",
                    required_dimensions = ["date"]):
                    
        self.cube = cube
        self.database = database
        self.fact_collection = fact_collection
        self.aggregate_flag_field = aggregate_flag_field

        if cube_collection:
            self.cube_collection = cube_collection
        else:
            self.cube_collection = fact_collection
            
        if required_dimensions:
            dims = []
            for dim in required_dimensions:
                dims.append(self.cube.dimension(dim))

        self.required_dimensions = dims
        self.measure_agg = None
        self.combined_points = None

        self.measure = measure
        
    def compute(self):
        """Find all dimensional points, compute cube for each point
        
        This is naive non-optimized method of cube computation: each point is computed separately.
        """

        print("==> Computing cube %s" % self.cube.name)

        combined_points = create_combined_dimension_points(self.cube.dimensions,
                                                            self.required_dimensions)

        print("--- got %d points" % len(combined_points))

        for point in combined_points:
            self.compute_cuboid(point)
                                                                
    def compute_cuboid(self, point):
        """ 
        From wdmmg.aggregator.compute_aggregations()
        """
        aggregates = {}
        print("Computing %s" % point)
        
        # cursor = self.fact_collection.find({self.aggregate_flag_field: {'$ne': True}})
        
        # for record in cursor:
        #     query_form = row.to_query_dict()
        #     axes_values = [query_form.get(a) for a in axes]
        #     _hash = repr(axes_values)
        #     common_fields, prev_amount, _ = aggregates.get(_hash, (None, 0.0, None))
        #     if common_fields is None:
        #         common_fields = dict(row.copy())
        #         del common_fields['_id']
        #     else:
        #         common_fields = dict_intersection(common_fields, row)
        #     amount = prev_amount + row.get('amount', 0)
        #     aggregates[_hash] = (common_fields, amount, axes_values)
        # 
        # key = _axes_query(axes)
        # for (entry, amount, values) in aggregates.values():
        #     query = dict(zip(axes, values))
        #     query.update(key)
        #     entry.update(key)
        #     entry['amount'] = amount 
        #     Entry.c.update(query, entry, upsert=True)
