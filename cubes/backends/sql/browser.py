# -*- coding=utf -*-
"""SQL Denormalized browser

Note: This browser will become obsolete once the star browser is implemented.
For more information about the upcoming browser see:

* star_browser.py
* in mapper.py see AttributeMapper and JoinFinder
"""

# FIXME: rename this to denormalized so backend name is "sql.denormalized"

import cubes.browser
import mapper
import logging
import cubes.model
import collections
from StringIO import StringIO

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict
    
from cubes.common import logger_name, get_logger
from collections import deque

try:
    import sqlalchemy
    import sqlalchemy.sql.expression as expression
    import sqlalchemy.sql.functions as functions
except ImportError:
    from cubes.common import MissingPackage
    _missing = MissingPackage("sqlalchemy", "Built-in SQL aggregation browser")
    sqlalchemy = expression = functions = _missing

__all__ = [
    "SQLBrowser",
    "CubeQuery"
]

# FIXME: required functionality TODO
# 
# * [DONE] number of items in drill-down
# * [DONE] dimension values
# * [DONE] drill-down sorting
# * [DONE] drill-down pagination
# * drill-down limits (such as top-10)
# * [DONE] facts sorting
# * [DONE] facts pagination
# * dimension values sorting
# * [DONE] dimension values pagination
# * remainder
# * ratio - aggregate sum(current)/sum(total) 
# * derived measures (should be in builder)

class FactsIterator(object):
    """
    Iterator that returns rows as dictionaries
    """
    def __init__(self, result):
        self.result = result
        self.batch = None

    def __iter__(self):
        return self

    def _fetch_batch(self):
        many = self.result.fetchmany()
        if not many:
            raise StopIteration
        self.batch = deque(many)
        # self.batch = [obj for obj in batch]
    def field_names(self):
        return self.result.keys()
        
    def next(self):
        if not self.batch:
            self._fetch_batch()

        row = self.batch.popleft()

        return dict(row.items())

class SQLBrowser(cubes.browser.AggregationBrowser):
    """Browser for aggregated cube computed by :class:`cubes.build.MongoSimpleCubeBuilder` """
    
    def __init__(self, cube, connection=None, view_name=None, schema=None,
                    view=None, locale=None):
        """Create a browser.
        
        :Attributes:
            * `cube` - cube object to be browsed
            * `connection` - sqlalchemy database connection object
            * `view_name` - name of denormalized view (might be VIEW or TABLE)
            * `view` - SLQ alchemy view/table object
            * `locale` - locale to be used for localized attributes

        To initialize SQL browser you should provide either a `connection`, `view_name` and optionally
        `shcema` or `view`.

        """
        super(SQLBrowser, self).__init__(cube)

        if not cube:
            raise Exception("Cube is not provided (should be not None)")

        self.cube = cube

        if (connection is None) and (view is None):
            raise Exception("SQLBrowser requires either connection or view to be provided.")

        if locale:
            self.locale = locale
        else:
            self.locale = cube.model.locale
        
        self.fact_key = cube.key
        if not self.fact_key:
            self.fact_key = mapper.DEFAULT_KEY_FIELD

        if connection is not None:
            # FIXME: This reflection is somehow slow (is there another way how to do it?)
            self.connection = connection
            self.view_name = view_name

            if not self.view_name:
                raise Exception("No view name specified for browser")
                
            self.engine = self.connection.engine
            metadata = sqlalchemy.MetaData(bind = self.engine)

            self.view = sqlalchemy.Table(self.view_name, metadata, autoload=True, schema=schema)
            self.key_column = self.view.c[self.fact_key]
        elif view is not None:
            self.connection = view.bind
            self.engine = self.connection.engine
            self.view = view
            self.key_column = self.view.c[self.fact_key]

        self.logger = logging.getLogger(logger_name)

    def aggregate(self, cell=None, measures=None, drilldown=None, order=None, **options):
        """See :meth:`cubes.browsers.cell.aggregate`."""

        cell = cell or cubes.browser.Cell(self.cube)
        result = cubes.browser.AggregationResult()
        result.cell = cell

        # Create query
        query = CubeQuery(cell, self.view, locale=self.locale)
        query.drilldown = drilldown
        query.order = order
        query.prepare()

        ############################################
        # Get summary
        cursor = self.engine.execute(query.summary_statement)
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
            
            rows = self.engine.execute(statement)
            # print "SQL:\n%s"% statement
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
            row_count = self.engine.execute(count_statement).fetchone()
            total_cell_count = row_count[0]

            result.drilldown = records
            result.total_cell_count = total_cell_count

        return result

    def facts(self, cell=None, order = None, **options):
        """Retruns iterable objects with facts"""
        # Create query

        cell = cell or cubes.browser.Cell(self.cube)
        query = CubeQuery(cell, self.view, locale = self.locale, **options)
        query.order = order
        query.prepare()
        statement = query.facts_statement

        page = options.get("page")
        page_size = options.get("page_size")

        if page is not None and page_size is not None:
            statement = statement.offset(page * page_size).limit(page_size)

        result = self.engine.execute(statement)

        return FactsIterator(result)
        
    def fact(self, key):
        """Fetch single row based on fact key"""

        cell = cubes.browser.Cell(self.cube)
        query = CubeQuery(cell, self.view, locale = self.locale)

        statement = query.fact_statement(key)

        cursor = self.engine.execute(statement)
        
        row = cursor.fetchone()
        if row:
            record = {}
            for (key, value) in row.items():
                record[key] = value
        else:
            record = None
            
        return record
        
    def values(self, cell, dimension, depth = None, order = None, **options):
        """Get values for dimension at given path within cell"""

        cell = cell or cubes.browser.Cell(self.cube)
        query = CubeQuery(cell, self.view, locale = self.locale, **options)
        query.order = order

        dimension = self.cube.dimension(dimension)
        statement = query.values_statement(dimension, depth)

        page = options.get("page")
        page_size = options.get("page_size")

        if page is not None and page_size is not None:
            statement = statement.offset(page * page_size).limit(page_size)

        rows = self.engine.execute(statement)

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
    """docstring for CubeQuery"""
    def __init__(self, cell, view, locale = None, **options):
        """Creates a cube query.
        
        :Attributes:
        
            * `cell` - cell within query will be executed
            * `view` - denormalized view/table where data is stored
            * `locale` - locale to be used for fetching data. if none specified, then default
              locale is used (first locale for attributes with multiple locales)

        .. note::
        
            This class requires refactoring for optimisation.
        """
        
        super(CubeQuery, self).__init__()
        self.cell = cell

        self.view = view
        self.condition_expression = None
        self.drilldown = None
        self.locale = locale

        self._last_levels = {}

        self.logger = logging.getLogger(logger_name)
        
        self._prepared = False

        self.cube = cell.cube
        self.cube_key = self.cube.key
        if not self.cube_key:
            self.cube_key = mapper.DEFAULT_KEY_FIELD

        self.key_column = self.view.c[self.cube_key]

        # FIXME: Refactor this! Remove unnecessary arrays
        # FIXME: Replace self._group_by with cell_attributes

        self._fact_columns = None
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
        if not self._fact_columns:
            self._prepare_fact_selection()

        condition = self.key_column == fact_id
        columns = [col.column for col in self.selection.values()]

        stmt = expression.select(columns, 
                                    whereclause = condition, 
                                    from_obj = self.view)
        return stmt

    @property
    def facts_statement(self):
        if not self._prepared:
            raise Exception("Query is not prepared")

        if not self._fact_columns:
            self._prepare_fact_selection()

        self._prepare_order()

        columns = [col.column for col in self.selection.values()]

        self._facts_statement = expression.select(columns, 
                                    whereclause = self._condition, 
                                    from_obj = self.view,
                                    order_by = self.order_by)

        return self._facts_statement

    def _prepare_fact_selection(self):
        self.selection = OrderedDict()

        column = self.column(self.cube_key)
        cellattr = CellAttribute(None, column.name, column)
        self.selection[column.name] = cellattr

        for measure in self.cube.measures:
            column = self.column(measure.name)
            cellattr = CellAttribute(measure, column.name, column)
            self.selection[column.name] = cellattr

        for attr in self.cube.details:
            column = self.column(attr.name)
            cellattr = CellAttribute(attr, column.name, column)
            self.selection[column.name] = cellattr

        # FIXME: missing (hybrid) cube detail attributes - not implemented yet

        for dimension in self.cube.dimensions:
            for level in dimension.default_hierarchy.levels:
                for attribute in level.attributes:
                    column = self.column(attribute, dimension)
                    cellattr = CellAttribute(attribute, column.name, column)
                    self.selection[column.name] = cellattr

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

    def values_statement(self, dimension, depth = None, hierarchy = None):
        """Get a statement that will select all values for dimension for `depth` levels. If
        depth is ``None`` then all levels are returned, that is all dimension values at all levels"""

        if not hierarchy:
            hierarchy = dimension.default_hierarchy
        levels = hierarchy.levels

        if depth == 0:
            raise ValueError("Depth for dimension values should not be 0")
        elif depth is not None:
            levels = levels[0:depth]
            
        self._prepare_condition()
        self.selection = OrderedDict()
        for level in levels:
            for attribute in level.attributes:
                column = self.column(attribute, dimension)
                cellattr = CellAttribute(attribute, column.name, column)
                self.selection[column.name] = cellattr

        self._prepare_order()

        columns = [col.column for col in self.selection.values()]

        values_statement = expression.select(columns,
                                    whereclause = self._condition,
                                    from_obj = self.view,
                                    group_by = columns,
                                    order_by = self.order_by)

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

        1. explicitly mentioned by calling browser methods
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

        for cut in self.cell.cuts:
            dim = self.cube.dimension(cut.dimension)
            if isinstance(cut, cubes.browser.PointCut):
                path = cut.path
                condition = self._point_condition(dim, path)
            elif isinstance(cut, cubes.browser.SetCut):
                conditions = []
                for path in cut.paths:
                    conditions.append(self._point_condition(dim, path))
                condition = expression.or_(*conditions)
            else:
                raise Exception("Only point and set cuts are supported in SQL browser at the moment")
            self._conditions.append(condition)
        
        self._condition = expression.and_(*self._conditions)
        
    def _point_condition(self, dim, path):
        """Adds a condition for `dimension` point at `path`."""
        conditions = [] 
        levels = dim.default_hierarchy.levels

        if len(path) > len(levels):
            raise Exception("Path has more items (%d: %s) than there are levels (%d) "
                            "in dimension %s" % (len(path), path, len(levels), dim.name))

        level = None
        for i, value in enumerate(path):
            level = levels[i]
            # Prepare condition: dimension.level_key = path_value
            column = self.column(level.key, dim)
            conditions.append(column == value)
            
            # Collect grouping columns
            for attr in level.attributes:
                column = self.column(attr, dim)
                self._group_by.append(column)
                cellattr = CellAttribute(attr, column.name, column)
                self.selection[column.name] = cellattr

        # Remember last level of cut dimension for further use, such as drill-down
        if level:
            self._last_levels[dim.name] = level

        return expression.and_(*conditions)
        
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
            self.logger.debug("converting drill-down specification to a dictionary")
            self._drilldown = {}

            for dim in self.drilldown:
                dim = self.cube.dimension(dim)
                next_level = self._next_drilldown_level(dim)
                self._drilldown[dim.name] = next_level
        elif isinstance(self.drilldown, dict):
            self.logger.debug("updating next levels in drill-down dictionary")

            # FIXME: shouldn't it be an ordered dictionary?
            self._drilldown = {}
            
            for dim, level in self.drilldown.items():
                dim = self.cube.dimension(dim)
                if level:
                    self._drilldown[dim.name] = level
                else:
                    next_level = self._next_drilldown_level(dim)
                    self._drilldown[dim.name] = next_level
        else:
            raise TypeError("Drilldown is of unknown type: %s" % self.drilldown.__class__)

    def _next_drilldown_level(self, dimension):
        """Get next drilldown level for dimension. If we are already cutting the dimension, then return
        next level to the last cut level. If we are not cutting, return first level."""
        
        # FIXME: only default hierarchy is currently used
        
        dim = self.cube.dimension(dimension)
        last_level = self._last_levels.get(dim.name)
        if last_level:
            next_level = dim.default_hierarchy.next_level(self._last_levels[dim.name])
            if not next_level:
                raise ValueError("Unable to drill-down after level '%s'. It is last level "
                                 "in default hierarchy in dimension '%s'" % 
                                 (last_level.name, dim.name))
        else:
            next_level = dim.default_hierarchy.levels[0]

        return next_level
        
    def column(self, field, dimension = None):
        """Return a table column for `field` which can be either :class:`cubes.Attribute` or a string.
        
        Possible column names:
        * ``field`` for fact field or flat dimension
        * ``field.locale`` for localized fact field or flat dimension
        * ``dimension.field`` for multi-level dimension field
        * ``dimension.field.locale`` for localized multi-level dimension field
        """

        # FIXME: should use: field.full_name(dimension, self.locale)
        # if there is no localization for field, use default name/first locale
        locale_suffix = ""

        if isinstance(field, cubes.model.Attribute) and field.locales:
            locale = self.locale if self.locale in field.locales else field.locales[0]
            locale_suffix = "." + locale

        if dimension:
            # FIXME: temporary flat dimension hack, not sure about impact of this to other parts of the
            # framework
            # FIXME: the third condition is a temporary quick fix for https://github.com/Stiivi/cubes/issues/14
            field_name = str(field)
            if not dimension.is_flat or dimension.has_details or dimension.name != field_name:
                logical_name = dimension.name + '.' + field_name
            else:
                logical_name = field_name
        else:
            logical_name = field

        self.logger.debug("getting column %s(%s) loc: %s - %s" % (field, type(field), self.locale, locale_suffix))

        localized_name = logical_name + locale_suffix

        column = self.view.c[localized_name]
        return expression.label(logical_name, column)

#
# Slicer server - backend handling
#

def ddl_for_model(url, model, fact_prefix=None, dimension_prefix=None, schema_type=None):
    """Create a star schema DDL for a model.
    
    Parameters:
    
    * `url` - database url – no connection will be created, just used by 
       SQLAlchemy to determine appropriate engine backend
    * `cube` - cube to be described
    * `dimension_prefix` - prefix used for dimension tables
    * `schema_type` - ignored in this backend
    
    As model has no data storage type information, following simple rule is
    used:
    
    * fact ID is an integer
    * all keys are strings
    * all attributes are strings
    * all measures are floats
    
    .. warning::
    
        Does not respect localized models yet.
    
    """
    dim_tables = {}
    dim_keys = {}
    
    out = StringIO()

    dimension_prefix = dimension_prefix or ""
    fact_prefix = fact_prefix or ""
    def dump(sql, *multiparams, **params):
        out.write(('%s' %
            sql.compile(dialect=engine.dialect)).strip()+';\n/\n')

    engine = sqlalchemy.create_engine(url, strategy='mock', executor=dump)

    metadata = sqlalchemy.MetaData(engine)

    # Create dimension tables
    
    for dim in model.dimensions:
        # If the dimension is represented by one field only, then there is
        # no need to create a separate table.
        if dim.is_flat and not dim.has_details:
            continue
        
        # Create and store constructed table name and key identifier. They
        # will be used in fact table creation
        
        name = dimension_prefix+dim.name
        dim_tables[dim.name] = name
        dim_key = dim.name + "_key"
        dim_keys[dim.name] = dim_key

        table = sqlalchemy.Table(name, metadata)
        table.append_column(sqlalchemy.Column(dim_key, sqlalchemy.Integer, primary_key=True))
        for attr in dim.all_attributes():
            table.append_column(sqlalchemy.Column(attr.name, sqlalchemy.String))
        
    # Create fact tables

    for cube in model.cubes.values():

        table = sqlalchemy.Table(fact_prefix+cube.name, metadata)
        table.append_column(sqlalchemy.Column(attr.name, sqlalchemy.Integer))

        for dim in cube.dimensions:
            if dim.is_flat and not dim.has_details:
                col = sqlalchemy.Column(dim.name, sqlalchemy.String)
            else:
                fkey = "%s.%s" % (dim_tables[dim.name], dim_keys[dim.name])
                col = sqlalchemy.Column(dim_keys[dim.name], sqlalchemy.Integer, sqlalchemy.ForeignKey(fkey), nullable=False)
            table.append_column(col)
    
        for attr in cube.details:
            table.append_column(sqlalchemy.Column(attr.name, sqlalchemy.String))
            
        for attr in cube.measures:
            table.append_column(sqlalchemy.Column(attr.name, sqlalchemy.Float))
    
    metadata.create_all()
    
    return out.getvalue()


def create_workspace(model, **options):
    """Create workspace for `model` with configuration in dictionary `config`. 
    This method is used by the slicer server."""

    try:
        dburl = options["url"]
    except KeyError:
        raise Exception("No URL specified in configuration")

    schema = options.get("schema")
    view_prefix = options.get("view_prefix")
    view_suffix = options.get("view_suffix")

    engine = sqlalchemy.create_engine(dburl)

    workspace = SQLWorkspace(model, engine, schema, 
                                    view_prefix = view_prefix,
                                    view_suffix = view_suffix)

    return workspace

class SQLWorkspace(object):
    """Factory for browsers"""
    def __init__(self, model, engine, schema=None, view_prefix=None, 
                 view_suffix=None):
        """Create a workspace"""
        super(SQLWorkspace, self).__init__()
        self.model = model
        self.engine = engine
        self.metadata = sqlalchemy.MetaData(bind=self.engine)
        self.view_prefix = view_prefix
        self.view_suffix = view_suffix
        self.views = {}
        self.schema = schema

        self.logger = cubes.get_logger()
        
    def browser_for_cube(self, cube, locale=None):
        """Creates, configures and returns a browser for a cube"""
        self.logger.info("workspace.create_browser() is depreciated, use "
                         ".browser() instead")

        return self.browser(cube, locale)

    def browser(self, cube, locale=None):
        cube = self.model.cube(cube)
        view = self._view_for_cube(cube)
        browser = SQLBrowser(cube, view=view, locale=locale)
        return browser
        
    def _view_for_cube(self, cube, view_name=None):
        if cube.name in self.views:
            view = self.views[cube.name]
        else:
            if cube.options:
                view_name = cube.options.get("denormalized_view") or view_name
                
            if not view_name:
                prefix = self.view_prefix or ""
                suffix = self.view_suffix or ""
                view_name = "%s%s%s" % (prefix, cube.name, suffix)

            view = sqlalchemy.Table(view_name, self.metadata, autoload = True, schema = self.schema)
            self.views[cube.name] = view            
            
        return view
