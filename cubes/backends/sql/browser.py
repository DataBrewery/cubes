import cubes.base
import base
import sqlalchemy
import sqlalchemy.sql.expression as expression
import sqlalchemy.sql.functions as functions
import logging

class SimpleSQLBrowser(cubes.base.AggregationBrowser):
    """Browser for aggregated cube computed by :class:`cubes.build.MongoSimpleCubeBuilder` """
    
    def __init__(self, cube, connection, view_name, schema = None):
        """Create a browser.
        
        :Attributes:
            * `cube` - cube object to be browsed
            * `connection` - sqlalchemy database connection object
            * `view_name` - name of denormalized view (might be VIEW or TABLE)

        """
        super(SimpleSQLBrowser, self).__init__(cube)

        self.cube = cube
        self.view_name = view_name

        self.fact_key = cube.key
        if not self.fact_key:
            self.fact_key = base.DEFAULT_KEY_FIELD

        if connection:
            self.connection = connection
            self.engine = self.connection.engine
            self.metadata = sqlalchemy.MetaData()
            self.metadata.bind = self.engine
            self.metadata.reflect()

            self.view = sqlalchemy.Table(self.view_name, self.metadata, autoload = True, schema = schema)
            self.key_column = self.view.c[self.fact_key]
        else:
            self.connection = None
            self.engine = None
            self.view = None
            self.key_column = None

        self.logger = logging.getLogger("brewery.cubes")
        
    def aggregate(self, cuboid, measures = None, drilldown = None):
        """See :meth:`cubes.browsers.Cuboid.aggregate`."""
        result = cubes.base.AggregationResult()
        
        # Create query
        query = CubeQuery(cuboid, self.view)
        query.drilldown = drilldown
        query.prepare()

        ############################################
        # Get summary
        row = self.connection.execute(query.summary_statement()).fetchone()
        summary = {}
        if row:
            for field in query.fields:
                summary[field] = row[field]

        result.summary = summary

        ############################################
        # Get drill-down
        #
        # FIXME: Change this to return some nice iterable
        #
        
        if drilldown:
            statement = query.drilldown_statement()
            # print("executing drill down statement")
            # print("%s" % str(statement))
            rows = self.connection.execute(statement)
            fields = query.fields + query.drilldown_fields
            records = []
            for row in rows:
                record = {}
                for field in fields:
                    record[field] = row[field]
                records.append(record)
            result.drilldown = records

        return result

    def facts(self, cuboid, **options):
        # Create query
        query = CubeQuery(cuboid, self.view, **options)

        query.prepare()
        statement = query.facts_statement()

        result = self.connection.execute(statement)

        # FIXME: Return nice iterable
        
        rows = []
        for row in result:
            record = {}
            for (key, value) in row.items():
                record[key] = value
            rows.append(record)

        return rows
        
    def fact(self, key):
        """Fetch single row based on fact key"""

        condition = self.key_column == key

        stmt = self.view.select(whereclause = condition)
        row = self.connection.execute(stmt).fetchone()
        if row:
            record = {}
            for (key, value) in row.items():
                record[key] = value
        else:
            record = None
            
        return record
        
class CubeQuery(object):
    """docstring for CuboidQuery"""
    def __init__(self, cuboid, view):
        """Creates a cube query.
        
        :Attributes:
        
            * `cuboid` - cuboid within query will be executed
        
        """
        
        super(CubeQuery, self).__init__()
        self.cuboid = cuboid
        self.cube = cuboid.cube
        self.view = view
        self.condition_expression = None
        self.drilldown = None

        self._last_levels = {}

        self.logger = logging.getLogger("brewery.cubes")
        
        self._prepared = False

        self.cube_key = self.cube.key
        if not self.cube_key:
            self.cube_key = base.DEFAULT_KEY_FIELD

        self.key_column = self.view.c[self.cube_key]

        self.fields = None

    def fact_statement(self, fact_id):        
        if not self._prepared:
            raise Exception("Query is not prepared")
            
        condition = self.key_column == fact_id

        stmt = expression.select(whereclause = condition, from_obj = self.view)
        return stmt

    def facts_statement(self):
        if not self._prepared:
            raise Exception("Query is not prepared")
        
        return self._facts_statement
        
    def summary_statement(self):
        if not self._prepared:
            raise Exception("Query is not prepared")
        
        return self._summary_statement

    def drilldown_statement(self):
        if not self._prepared:
            raise Exception("Query is not prepared")

        return self._drilldown_statement

    def prepare(self):
        """Prepare star query statement"""
        
        self.logger.info("preparing query")
        
        self.conditions = []

        self.group_by = []
        self.selection = []
        self.fields = []

        self._last_levels = {}

        ################################################################
        # 1. Collect conditions and grouping fields

        for cut in self.cuboid.cuts:
            if not isinstance(cut, cubes.base.PointCut):
                raise Exception("Only point cuts are supported in SQL browser at the moment")
            
            dim = self.cube.dimension(cut.dimension)
            path = cut.path
            levels = dim.default_hierarchy.levels

            if len(path) > len(levels):
                raise Exception("Path has more items (%d) than there are levels (%d) "
                                "in dimension %s" % (len(path), len(levels), dim.name))

            level = None
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

            # Remember last level of cut dimension for further use, such as drill-down
            if level:
                self._last_levels[dim.name] = level

        ################################################################
        # Prepare drill-down
        
        if self.drilldown:
            self._prepare_drilldown()
                    
        ################################################################
        # Prepare select expressions

        selection = self.selection[:]
        for measure in self.cube.measures:
            label = str(measure) + "_sum"
            s = functions.sum(self.column(str(measure))).label(label)
            selection.append(s)
            self.fields.append(label)

        rcount_label = "record_count"
        rcount = functions.count().label(rcount_label)
        self.fields.append(rcount_label)
        selection.append(rcount)

        self.condition = expression.and_(*self.conditions)

        self._facts_statement = self.view.select(whereclause = self.condition)

        self._summary_statement = expression.select(selection, 
                                whereclause = self.condition, 
                                from_obj = self.view,
                                group_by = self.group_by)
        if self.drilldown:
            drilldown_selection = selection + self.drilldown_selection
            drilldown_group_by = self.group_by + self.drilldown_group_by

            self._drilldown_statement = expression.select(drilldown_selection, 
                                        whereclause = self.condition, 
                                        from_obj = self.view,
                                        group_by = drilldown_group_by)
        self._prepared = True
        
    def _prepare_drilldown(self):
        """Prepare drill down selection, groupings and fields"""
        
        self.logger.info("preparing drill-down")
        self.drilldown_group_by = []
        self.drilldown_selection = []
        self.drilldown_fields = []

        self._normalize_drilldown()

        self.logger.debug("drilldown: %s" % self._drilldown)

        for dim_obj, level_obj in self._drilldown.items():
            # Get dimension object, just in case it is specified as string in drilldown
            dim = self.cube.dimension(dim_obj)
            drill_level = dim.level(level_obj)
            
            # We need to get all additional levels between last level and drill level
            levels = []
            collect = False
            hier_levels = dim.default_hierarchy.levels

            index = hier_levels.index(drill_level)
            levels = hier_levels[0:index+1]
                            
            for level in levels:
                for attr in level.attributes:
                    self.logger.debug("adding drill down attribute %s.%s" % (dim.name, attr))
                    column = self.column(attr, dim)
                    if column not in self.group_by:
                        self.drilldown_group_by.append(column)
                    if column not in self.selection:
                        self.drilldown_selection.append(column)
                    if column.name not in self.fields:
                        self.drilldown_fields.append(column.name)

    def _normalize_drilldown(self):
        """ Normalize drilldown variable: if it is list or tuple, then "next level" is
        considered"""

        if type(self.drilldown) == list or type(self.drilldown) == tuple:
            self.logger.debug("normalizing drill-down")
            self._drilldown = {}

            for obj in self.drilldown:
                dim = self.cube.dimension(obj)
                last_level = self._last_levels.get(dim.name)

                if last_level:
                    next_level = dim.default_hierarchy.next_level(self._last_levels[dim.name])
                    if not next_level:
                        raise ValueError("Unable to drill-down after level '%s'. It is last level "
                                         "in default hierarchy in dimension '%s'" % 
                                         (last_level.name, dim.name))
                else:
                    next_level = dim.default_hierarchy.levels[0]

                self.logger.debug("dimension %s last level: %s next: %s" % (dim.name, last_level, next_level.name))
                self._drilldown[dim.name] = next_level
        elif isinstance(self.drilldown, dict):
            self.logger.debug("no normalization of drill-down required")
            self._drilldown = self.drilldown
        else:
            raise TypeError("Drilldown is of unknown type: %s" % self.drilldown.__class__)
        
    def column(self, field, dimension = None):
        if dimension:
            name = dimension.name + '.' + str(field)
        else:
            name = field

        return self.view.c[name]
        