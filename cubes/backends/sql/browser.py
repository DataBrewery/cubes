import cubes.browser
import base
import logging
import cubes.model
import collections
from collections import OrderedDict

try:
    import sqlalchemy
    import sqlalchemy.sql.expression as expression
    import sqlalchemy.sql.functions as functions
except:
    pass
    
# FIXME: required functionality TODO
# 
# * [DONE] number of items in drill-down
# * [DONE] dimension values
# * [DONE] drill-down sorting
# * [DONE] drill-down pagination
# * drill-down limits (such as top-10)
# * facts sorting
# * [DONE] facts pagination
# * dimension values sorting
# * [DONE] dimension values pagination
# * remainder
# * ratio - aggregate sum(current)/sum(total) 

class SQLBrowser(cubes.browser.AggregationBrowser):
    """Browser for aggregated cube computed by :class:`cubes.build.MongoSimpleCubeBuilder` """
    
    def __init__(self, cube, connection, view_name, schema = None, locale = None):
        """Create a browser.
        
        :Attributes:
            * `cube` - cube object to be browsed
            * `connection` - sqlalchemy database connection object
            * `view_name` - name of denormalized view (might be VIEW or TABLE)
            * `locale` - locale to be used for localized attributes

        """
        super(SQLBrowser, self).__init__(cube)

        self.cube = cube
        self.view_name = view_name

        if locale:
            self.locale = locale
        else:
            self.locale = cube.model.locale
        
        self.fact_key = cube.key
        if not self.fact_key:
            self.fact_key = base.DEFAULT_KEY_FIELD

        if connection:
            
            # FIXME: This reflection is somehow slow (is there anotherway how to do it?)
            self.connection = connection
            self.engine = self.connection.engine
            self.metadata = sqlalchemy.MetaData(bind = self.engine)

            self.view = sqlalchemy.Table(self.view_name, self.metadata, autoload = True, schema = schema)
            self.key_column = self.view.c[self.fact_key]
        else:
            self.connection = None
            self.engine = None
            self.view = None
            self.key_column = None

        self.logger = logging.getLogger("brewery.cubes")

    def aggregate(self, cuboid, measures = None, drilldown = None, order = None, **options):
        """See :meth:`cubes.browsers.Cuboid.aggregate`."""
        result = cubes.browser.AggregationResult()
        
        # Create query
        query = CubeQuery(cuboid, self.view, locale = self.locale)
        query.drilldown = drilldown
        query.order = order
        query.prepare()

        ############################################
        # Get summary
        cursor = self.connection.execute(query.summary_statement)
        row = cursor.fetchone()
        summary = {}
        if row:
            for field in query.summary_selection.keys():
                summary[field] = row[field]
        cursor.close()
        result.summary = summary

        ############################################
        # Get drill-down
        #
        # FIXME: Change this to return some nice iterable
        #
        
        if drilldown:
            statement = query.drilldown_statement

            page = options.get("page")
            page_size = options.get("page_size")

            if page is not None and page_size is not None:
                statement = statement.offset(page * page_size).limit(page_size)
            
            rows = self.connection.execute(statement)
            
            # FIXME: change this into iterable, do not fetch everythig - we want to get plain dict
            # fields = query.fields + query.drilldown_fields
            fields = [attr.name for attr in query.selection.values()]
            records = []
            for row in rows:
                record = {}
                for field in fields:
                    field = str(field)
                    record[field] = row[str(field)]
                records.append(record)

            count_statement = query.full_drilldown_statement.alias().count()
            row_count = self.connection.execute(count_statement).fetchone()
            total_cell_count = row_count[0]

            result.drilldown = records
            result.total_cell_count = total_cell_count

        return result

    def facts(self, cuboid, **options):
        # Create query
        query = CubeQuery(cuboid, self.view, locale = self.locale, **options)

        query.prepare()
        statement = query.facts_statement

        page = options.get("page")
        page_size = options.get("page_size")

        if page is not None and page_size is not None:
            statement = statement.offset(page * page_size).limit(page_size)

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

        # stmt = expression.select(columns,
        #                             whereclause = condition,
        #                             from_obj = self.view)

        cursor = self.connection.execute(stmt)
        
        row = cursor.fetchone()
        if row:
            record = {}
            for (key, value) in row.items():
                record[key] = value
        else:
            record = None
            
        return record
        
    def values(self, cuboid, dimension, depth = None, **options):
        """Get values for dimension at given path within cuboid"""

        dimension = self.cube.dimension(dimension)
        query = CubeQuery(cuboid, self.view, locale = self.locale, **options)

        statement = query.values_statement(dimension, depth)

        page = options.get("page")
        page_size = options.get("page_size")

        if page is not None and page_size is not None:
            statement = statement.offset(page * page_size).limit(page_size)

        rows = self.connection.execute(statement)

        fields = rows.keys()
        
        records = []
        for row in rows:
            record = {}
            for field in fields:
                record[field] = row[field]
            records.append(record)
            
        return records

CellAttribute = collections.namedtuple("CellAttribute", "attribute, name, column")

class CubeQuery(object):
    """docstring for CuboidQuery"""
    def __init__(self, cuboid, view, locale = None, **options):
        """Creates a cube query.
        
        :Attributes:
        
            * `cuboid` - cuboid within query will be executed
            * `view` - denormalized view/table where data is stored
            * `locale` - locale to be used for fetching data. if none specified, then default
              locale is used (first locale for attributes with multiple locales)

        .. note::
        
            This class requires refactoring for optimisation.
        """
        
        super(CubeQuery, self).__init__()
        self.cuboid = cuboid
        self.cube = cuboid.cube
        self.view = view
        self.condition_expression = None
        self.drilldown = None
        self.locale = locale

        self._last_levels = {}

        self.logger = logging.getLogger("brewery.cubes")
        
        self._prepared = False

        self.cube_key = self.cube.key
        if not self.cube_key:
            self.cube_key = base.DEFAULT_KEY_FIELD

        self.key_column = self.view.c[self.cube_key]

        # FIXME: Refactor this! Remove unnecessary arrays
        # FIXME: Replace self._group_by with cell_attributes

        self._conditions = []
        self._condition = None
        self._group_by = []
        self._last_levels = {}
        self.summary_selection = OrderedDict()
        self.selection = OrderedDict()
        
        self.page = None
        self.page_size = None
        self._order = OrderedDict()

    @property
    def order(self):
        return self._order
        
    @order.setter
    def order(self, order):
        """Set order. Oder should be a list of tuples (field, order). If only string is provided,
        then it is converted to (string, None)."""
        self._order = OrderedDict()
        if order is not None:
            for item in order:
                if isinstance(item, basestring):
                    self._order[item] = None
                else:
                    self._order[item[0]] = item[1]

    def fact_statement(self, fact_id):        
        if not self._prepared:
            raise Exception("Query is not prepared")
            
        condition = self.key_column == fact_id

        stmt = expression.select(whereclause = condition, from_obj = self.view)
        return stmt

    @property
    def facts_statement(self):
        if not self._prepared:
            raise Exception("Query is not prepared")
        
        return self._facts_statement
        
    @property
    def summary_statement(self):
        if not self._prepared:
            raise Exception("Query is not prepared")
        
        return self._summary_statement

    @property
    def full_drilldown_statement(self):
        """Return a drill-down statement that will return all cells without limit"""
        if not self._prepared:
            raise Exception("Query is not prepared")

        return self._drilldown_statement

    @property
    def drilldown_statement(self):
        """Return a drill-down statement that will return limited cells (like "top 10")"""
        if not self._prepared:
            raise Exception("Query is not prepared")

        return self._drilldown_statement

    def values_statement(self, dimension, depth = None):
        """Get a statement that will select all values for dimension for `depth` levels. If
        depth is ``None`` then all levels are returned, that is all dimension values at all levels"""

        levels = dimension.default_hierarchy.levels

        if depth is not None:
            levels = levels[0:depth]
            
        self._prepare_condition()

        selection = []
        for level in levels:
            for attribute in level.attributes:
                column = self.column(attribute, dimension)
                selection.append(column)

        values_statement = expression.select(selection,
                                    whereclause = self._condition,
                                    from_obj = self.view,
                                    group_by = selection)

        return values_statement

    def prepare(self):
        """Prepare star query statement"""
        
        self.logger.info("preparing query")

        # 1. Collect conditions and grouping fields
        self._prepare_condition()

        # 2. Prepare drill-down
        if self.drilldown:
            self._prepare_drilldown()
                    
        self._prepare_aggregations()

        ################################################################
        # Prepare select expressions

        ##########################
        ## -- 1 -- FACTS
        self._facts_statement = self.view.select(whereclause = self._condition)

        columns = [col.column for col in self.selection.values()]

        ##########################
        ## -- 2 -- SUMMARY
        self._summary_statement = expression.select(columns, 
                                whereclause = self._condition, 
                                from_obj = self.view,
                                group_by = self._group_by)
        self.summary_selection = OrderedDict(self.selection)

        ##########################
        ## -- 2 -- DRILL DOWN
        if self.drilldown:
            self.selection.update(self.drilldown_selection)

            drilldown_group_by = self._group_by + self.drilldown_group_by

            self._prepare_order()

            columns = [col.column for col in self.selection.values()]
            
            self._drilldown_statement = expression.select(columns, 
                                        whereclause = self._condition, 
                                        from_obj = self.view,
                                        group_by = drilldown_group_by,
                                        order_by = self.order_by)

        self._prepared = True

    def _prepare_aggregations(self):
        """Collect measures and create aggregation fields.
        """
        for measure in self.cube.measures:
            label = str(measure) + "_sum"
            s = functions.sum(self.column(str(measure))).label(label)
            cellattr = CellAttribute(None, label, s)
            self.selection[label] = cellattr

        rcount_label = "record_count"
        rcount = functions.count().label(rcount_label)
        cellattr = CellAttribute(None, rcount_label, rcount)
        self.selection[rcount_label] = cellattr

    def _prepare_order(self):
        """Prepare ORDER BY expression.

        There are two sources of ordering information:

        1. explicitly mentionaed by calling browser methods
        2. implicitly specified in the model attributes (natural order)
        
        The final ordering is:
            explicitly mentioned + (natural order - explicitly mentioned)
        
        Explicitly specified attribute order replaces implicitly specified.
        """
        
        # Collect explicit order atributes
        
        # 'ordering' values will be tuples: (CellAttribute, order)
        ordering = OrderedDict()
        for field, order in self._order.items():
            if field in self.selection:
                ordering[field] = (self.selection[field], order)

        # Collect natural (default) order attributes, skip those that are explicitly mentioned
        for cell_attr in self.selection.values():
            if cell_attr.attribute and cell_attr.name not in ordering:
                ordering[cell_attr.name] = (cell_attr, cell_attr.attribute.order)
                
        # print "ORDER: %s" % ordering
        # natural_order = [a for a in self.selection.values()
        #                         if a.attribute and a.attribute.order and
        #                             a.name not in self._order_fields]
        # 
        # order_attributes = ex_order_attribs + natural_order
        
        # Construct ORDER BY:
        self.order_by = []
        for (attr, order) in ordering.values():
            column = attr.column
            if order:
                if order.lower().startswith("asc"):
                    column = column.asc()
                elif order.lower().startswith("desc"):
                    column = column.desc()
            self.order_by.append(column)
        
                                    
    def _prepare_condition(self):
        self._conditions = []
        self._group_by = []

        for cut in self.cuboid.cuts:
            if not isinstance(cut, cubes.browser.PointCut):
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
                self._conditions.append(column == value)
                
                # Collect grouping columns
                for attr in level.attributes:
                    column = self.column(attr, dim)
                    self._group_by.append(column)
                    cellattr = CellAttribute(attr, column.name, column)
                    self.selection[column.name] = cellattr

            # Remember last level of cut dimension for further use, such as drill-down
            if level:
                self._last_levels[dim.name] = level

        self._condition = expression.and_(*self._conditions)
        
    def _prepare_drilldown(self):
        """Prepare drill down selection, groupings and fields"""
        
        self.logger.info("preparing drill-down")
        self.drilldown_group_by = []
        self.drilldown_selection = OrderedDict()
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
                    cellattr = CellAttribute(attr, column.name, column)
                    if column not in self._group_by:
                        self.drilldown_group_by.append(column)
                    if column.name not in self.selection:
                        self.drilldown_selection[column.name] = cellattr

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

    # def attribute(self, field):
    #     """Return Attribute object based on field specification."""
    #     if isinstance(field, cubes.model.Attribute):
    #         return field
    #         
    #     split = field.split(".")
    #     if len(split) == 1:
        
    def column(self, field, dimension = None):
        # FIXME: should use: field.full_name(dimension, self.locale)
        # if there is no localization for field, use default name/first locale
        locale_suffix = ""

        if dimension:
            if isinstance(field, cubes.model.Attribute) and field.locales:
                if self.locale in field.locales:
                    locale = self.locale
                else:
                    locale = field.locales[0]
                locale_suffix = "." + locale
            logical_name = dimension.name + '.' + str(field)
        else:
            logical_name = field

        localized_name = logical_name + locale_suffix
        column = self.view.c[localized_name]
        return expression.label(logical_name, column)
        