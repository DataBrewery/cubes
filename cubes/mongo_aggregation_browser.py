import aggregation_browser
import itertools

try:
    import pymongo
    import bson
except ImportError:
    pass

class MongoAggregationBrowser(aggregation_browser.AggregationBrowser):
    """MongoDB Aggregation Browser"""
        
    def __init__(self, cube, collection):
        """Create mongoDB Aggregation Browser
        """
        super(MongoAggregationBrowser, self).__init__(cube)
        self.collection = collection
    
    def aggregate(self, cuboid, measure):

        values = {
            "collection": "entity",
            "dimension_list": "time:this.time",
            "measure_agg": "amount_sum",
            "measure": "amount"
        }

        map_function = '''
        function() {
            emit(
                {%(dimension_list)s},
                {%(measure_agg)s: this.%(measure)s, record_count:1}
            );
        }''' % values

        reduce_function = '''
        function(key, vals) {
            var ret = {%(measure_agg)s:0, record_count:1};
            for(var i = 0; i < vals.length; i++) {
                ret.%(measure_agg)s += vals[i].%(measure_agg)s;
                ret.record_count += vals[i].record_count;
            }
            return ret;
        }\n''' % values

        print("--- MAP: %s" % map_function)
        print("--- REDUCE: %s" % reduce_function)

        map_reduce = '''
        db.runCommand({
        mapreduce: "entry",
        map: %(map)s,
        reduce: %(reduce)s,
        out: { inline : 1}
        })
        '''
        code = bson.code.Code(map_reduce)


        output = "{ inline : 1}"
        map_code = bson.code.Code(map_function)
        reduce_code = bson.code.Code(reduce_function)

        # result = self.collection.map_reduce(map_code, reduce_code, out = 'cube')
        result = self.collection.database.command("mapreduce", "entry",
                                            map = map_function,
                                            reduce = reduce_function,
                                            out = { "inline" : 1 })
        return result

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
        
        self.combined_points = None

        self.measure = measure
    
    def compute(self):
        """Brute-force cube computation - no reuse of precomputed aggregates"""

        print("--> Computing cube %s" % self.cube.name)

        print("--> creating point combinations")
        self.create_combined_points()

        print("--> truncating cube")
        self.database[self.cube_collection].remove()

        print("--> computing points")
        for point in self.combined_points:
            self.compute_point(point)
    
    def compute_point(self, point):
        print "--- point:"


        ################################################################
        # 1. Create map function
        
        groupers = []
        for dimpoint in point:
            dim = dimpoint[0]
            print "---     dim: %s" % dim.name
            mapped_keys = []
            for level_name in dimpoint[1]:
                print "---     level: %s" % level_name
                level = dim.level(level_name)
                mapped_key = self.cube.dimension_field_mapping(dim, level.key)
                mapped_keys.append(mapped_key[0])
            
            mapped_keys = ["this." + key for key in mapped_keys]
            
            string = ", ".join(mapped_keys)
            grouper = "%s: [%s]" % (dim.name, string)
            groupers.append(grouper)
    

        # FIXME: allow more aggregations and aggregation types
        measure_agg = self.measure + "_sum"

        groupers_str = ", ".join(groupers)

        parameters = { "groupers": groupers_str, 
                       "measure_agg": measure_agg,
                       "measure": self.measure }

        map_function = '''
        function() {
            emit(
                {%(groupers)s},
                {%(measure_agg)s: this.%(measure)s, record_count:1}
            );
        }''' % parameters
        
        ################################################################
        # 2. Create reduce function
        
        reduce_function = '''
        function(key, vals) {
            var ret = {%(measure_agg)s:0, record_count:1};
            for(var i = 0; i < vals.length; i++) {
                ret.%(measure_agg)s += vals[i].%(measure_agg)s;
                ret.record_count += vals[i].record_count;
            }
            return ret;
        }\n''' % parameters

        ################################################################
        # 3. Run map-reduce
        print "--> Running map-reduce"
        print "--- MAP: \n%s\n" % (map_function)
        result = self.database.command("mapreduce", self.fact_collection,
                                            map = map_function,
                                            reduce = reduce_function,
                                            out = { "merge" : self.cube_collection })

    
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
        