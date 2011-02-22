import cubes.base as base
import sqlalchemy
import sqlalchemy.sql.expression as expression
import sqlalchemy.sql.functions as functions

class SimpleSQLBrowser(base.AggregationBrowser):
    """Browser for aggregated cube computed by :class:`cubes.build.MongoSimpleCubeBuilder` """
    
    def __init__(self, cube, connection, view_name, schema = None):
        """Create a browser.
        
        :Attributes:
            * `cube` - cube object to be browsed
            * `connection` - sqlalchemy database connection object
            * `view_name` - name of denormalized view (might be VIEW or TABLE)

        """
        super(SimpleSQLBrowser, self).__init__(cube)

        self.view_name = view_name

        if connection:
            self.connection = connection
            self.engine = self.connection.engine
            self.metadata = sqlalchemy.MetaData()
            self.metadata.bind = self.engine
            self.metadata.reflect()

            self.view = sqlalchemy.Table(self.view_name, self.metadata, autoload = True, schema = schema)
        else:
            self.connection = None
            self.engine = None
            self.view = None

        self.schema = schema

        self.cube = cube
        
        
    def aggregate(self, cuboid, measures = None, drill_down = None):
        """See :meth:`cubes.browsers.Cuboid.aggregate`."""
        
        # Create query
        query = CubeQuery(cuboid, self.view)
        print "EXECUTING SQL: %s" % str(query.aggregate_statement())
        row = self.connection.execute(query.aggregate_statement()).fetchone()
        summary = {}
        if row:
            for field in query.fields:
                summary[field] = row[field]

        result = base.AggregationResult()
        result.summary = summary
        
        return result
        
    def selected_fields(self, cuboid):
        selected_fields = []
        for cut in cuboid.cuts:
            if not isinstance(cut, base.PointCut):
                raise Exception("Only point cuts are supported in SQL browser at the moment")
            
            for dimension in cut.dimensions:
                for level in dimension.default_hierarchy.levels:
                    for attribute in level.attributes:
                        field = dimension.name + "." + attribute
                        selected_fields.append(field)
                        
        return selected_fields
        
class CubeQuery(object):
    """docstring for CuboidQuery"""
    def __init__(self, cuboid, view):
        super(CubeQuery, self).__init__()
        self.cuboid = cuboid
        self.cube = cuboid.cube
        self.view = view
        self.condition_expression = None
        self.fields = None
        
    def fact_statement(self, fact_id):        
        self._prepare()

        key_condition = self.key_column == fact_id

        if self.conditions:
            condition = expression.and_(self.condition, key_condition)
        else:
            condition = key_condition
        
        stmt = expression.select(whereclause = condition, from_obj = self.view)
        return stmt

    def aggregate_statement(self):
        self._prepare()
        
        selection = self.selection[:]
        for measure in self.cube.measures:
            label = measure + "_sum"
            s = functions.sum(self.column(measure)).label(label)
            selection.append(s)
            self.fields.append(label)

        rcount_label = "record_count"
        rcount = functions.count().label(rcount_label)
        self.fields.append(rcount_label)
        selection.append(rcount)

        stmt = expression.select(selection, 
                                 whereclause = self.condition, 
                                 from_obj = self.view,
                                 group_by = self.group_by)
        
        return stmt

    def _prepare(self):
        self.conditions = []
        self.group_by = []
        self.selection = []
        self.fields = []

        for cut in self.cuboid.cuts:
            if not isinstance(cut, base.PointCut):
                raise Exception("Only point cuts are supported in SQL browser at the moment")
            
            dim = self.cube.dimension(cut.dimension)
            path = cut.path
            levels = dim.default_hierarchy.levels

            if len(path) > len(levels):
                raise Exception("Path has more items (%d) than there are levels (%d) "
                                "in dimension %s" % (len(path), len(levels), dim.name))

            for i, value in enumerate(path):
                level = levels[i]
                # Prepare condition: dimension.level_key = path_value
                column = self.column(level.key, dim)
                self.conditions.append(column == value)
                
                # Collect grouping columns
                for attr in level.attributes:
                    column = self.column(attr, dim)
                    self.group_by.append(column)
                    self.selection.append(column)
                    self.fields.append(column.name)
                    
        self.condition = expression.and_(*self.conditions)
        
    def column(self, field, dimension = None):
        if dimension:
            name = dimension.name + '.' + field
        else:
            name = field

        return self.view.c[name]

    @property
    def key_column(self):
        return self.view.c["id"]
        