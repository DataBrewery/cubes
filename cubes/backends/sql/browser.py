from cubes.base import *
import sqlalchemy

class SimpleSQLBrowser(AggregationBrowser):
    """Browser for aggregated cube computed by :class:`cubes.build.MongoSimpleCubeBuilder` """
    
    def __init__(self, cube, connection, view_name, schema = None):
        """Create a browser.
        
        :Attributes:
            * `cube` - cube object to be browsed
            * `connection` - sqlalchemy database connection object
            * `view_name` - name of denormalized view (might be VIEW or TABLE)

        """
        super(SimpleSQLBrowser, self).__init__(cube)

        self.connection = connection
        self.view_name = view_name

        self.connection = connection
        self.engine = self.connection.engine
        
        self.metadata = sqlalchemy.MetaData()
        self.metadata.bind = self.engine
        self.metadata.reflect()
        self.schema = schema

        self.table = sqlalchemy.Table(self.view_name, self.metadata, autoload = True, schema = schema)
        
    def aggregate(self, cuboid, measures = None, drill_down = None):
        """See :meth:`cubes.browsers.Cuboid.aggregate`."""
        
        ###################################################
        # 1. Prepare cuboid selector

        if drill_down:
            drill_dimension = self.cube.dimension(drill_down)
        else:
            drill_dimension = None
            
        selector = self.selector_object(cuboid, drill_dimension)
        condition = { self.cuboid_selector_name: selector }
        condition[self.aggregate_flag_field] = True
        
        if drill_down:
            drill_dimension = self.cube.dimension(drill_down)
        else:
            drill_dimension = None

        ###################################################
        # 2. Prepare dimension filter conditions
        
        dim_conditions = {}
        for cut in cuboid.cuts:
            if type(cut) != PointCut:
                raise AttributeError("only point cuts are currently supported for mongo aggregation browsing")

            dimension = self.cube.dimension(cut.dimension)
            path = cut.path

            dim_levels = dimension.default_hierarchy.levels

            # Get physical field names from field mappings specified in cube and use them
            # in selection condition
            for i, value in enumerate(path):
                level = dim_levels[i]
                mapped = base.dimension_field_mapping(self.cube, dimension, level.key)
                dim_conditions[mapped[0]] = value
                
        # Expand dictionary: convert key1.key2 = value into 'key1 : { key2 : value}'
        dim_conditions = cubes.util.expand_dictionary(dim_conditions)
        condition.update(dim_conditions)
        
        ###################################################
        # 3. Perform selection - find records in collection
        
        cursor = self.collection.find(spec = condition)
        return cursor
