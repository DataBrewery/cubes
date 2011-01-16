import base
import cubes.utils

class MongoPreaggregatedBrowser(base.AggregationBrowser):
    """Browser for aggregated cube computed by :class:`cubes.builders.MongoSimpleCubeBuilder` """
    
    def __init__(self, cube, collection, database = None, aggregate_flag_field = "_is_aggregate"):
        """Create a browser.
        
        :Attributes:
            * `cube` - cube object to be browsed
            * `collection` - MongoDB collection object or name of a collection
            * `database` - MongoDB database. Has to be specified if `collection` is a name
            * `aggregate_flag_field` - field to identify aggregated records. By default it is 
              ``'_is_aggregate'``
        
        """
        super(MongoPreaggregatedBrowser, self).__init__(cube)

        if type(collection) == str:
            if not database:
                raise AttributeError("Collection reference '%s' provided as name (string), but no MongoDB "\
                                     "database connection specified", collection)
            self.collection = database[collection]
        else:
            self.collection = collection
        
        self.aggregate_flag_field = aggregate_flag_field
        self.cuboid_selector_name = "_cuboid"

    def aggregate(self, cuboid, measures = None, drill_down = None):
        """See :meth:`cubes.browsers.Cuboid.aggregate`."""
        
        ###################################################
        # 1. Prepare cuboid selector

        selector = self.selector_object(cuboid)
        condition = { self.cuboid_selector_name: selector }
        condition[self.aggregate_flag_field] = True
        
        ###################################################
        # 2. Prepare dimension filter conditions
        
        dim_conditions = {}
        for cut in cuboid.cuts:
            if type(cut) != base.PointCut:
                raise AttributeError("only point cuts are currently supported for mongo aggregation browsing")

            dimension = self.cube.dimension(cut.dimension)
            path = cut.path

            # FIXME: allow use of other hierarchies as well (requires precomputation)
            dim_levels = dimension.default_hierarchy.levels

            # Get physical field names from field mappings specified in cube and use them
            # in selection condition
            for i, value in enumerate(path):
                level = dim_levels[i]
                mapped = self.cube.dimension_field_mapping(dimension, level.key)
                dim_conditions[mapped[0]] = value
                
        # Expand dictionary: convert key1.key2 = value into 'key1 : { key2 : value}'
        dim_conditions = cubes.utils.expand_dictionary(dim_conditions)
        
        condition.update(dim_conditions)
        ###################################################
        # 3. Perform selection - find records in collection
        
        cursor = self.collection.find(spec = condition)
        print condition
        return cursor

    def selector_object(self, cuboid):
        selector = {}
        for cut in cuboid.cuts:
            if type(cut) != base.PointCut:
                raise AttributeError("only point cuts are currently supported for mongo aggregation browsing")
            
            dimension = self.cube.dimension(cut.dimension)
            dim_levels = dimension.default_hierarchy.levels
            levels = dim_levels[0:len(cut.path)]
            
            level_names = [level.name for level in levels]
            selector[dimension.name] = level_names
            
        return selector