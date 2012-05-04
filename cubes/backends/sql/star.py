# -*- coding=utf -*-
from cubes.browser import *
from cubes.common import get_logger
from cubes.backends.sql.common import Mapper
from cubes.backends.sql.common import DEFAULT_KEY_FIELD
import logging
import collections

try:
    import sqlalchemy
    import sqlalchemy.sql as sql
except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = MissingPackage("sqlalchemy", "Built-in SQL aggregation browser")

# Required functionality checklist
# 
# * [done] fact
# * [partial] facts in a cell
# *     [done] pagination
# *     [done] ordering
# * [partial] aggregation
# *     [done] drill-down
# *     [done] drill-down pagination
# *     [done] number of total items in drill-down
# *     [done] drill-down ordering
# *     [ ] drill-down limits (such as top-10)
# *     [ ] remainder
# * [ ] ratio - aggregate sum(current)/sum(total) 
# * [ ] derived measures
# * [partial] dimension values
# *     [done] pagination
# *     [done] ordering

__all__ = ["StarBrowser"]

# Browsing context:
#     * engine
#     * metadata
#
#     * locale
#
#     * fact name
#     * dimension table prefix
#     * schema

class StarBrowser(AggregationBrowser):
    """docstring for StarBrowser"""

    def __init__(self, cube, connectable=None, locale=None, dimension_prefix=None,
                fact_prefix=None, schema=None, metadata=None, debug=False):
        """StarBrowser is a SQL-based AggregationBrowser implementation that 
        can aggregate star and snowflake schemas without need of having 
        explicit view or physical denormalized table.

        Attributes:

        * `cube` - browsed cube
        * `connectable` - SQLAlchemy connectable object (engine or connection)
        * `dimension_prefix` - prefix for dimension tables
        * `fact_prefix` - prefix for fact tables (`prefix`+`cube.name`)
        * `schema` - default database schema name
        * `locale` - locale used for browsing
        * `metadata` - SQLAlchemy MetaData object
        * `debug` - output SQL to the logger at INFO level

        .. warning:

            Not fully implemented yet.

        **Limitations:**

        * only one locale can be used for browsing at a time
        * locale is implemented as denormalized: one column for each language
        """
        super(StarBrowser, self).__init__(cube)

        if cube == None:
            raise Exception("Cube for browser should not be None.")

        self.logger = get_logger()

        self.cube = cube
        self.locale = locale
        self.debug = debug

        if connectable is not None:
            self.connectable = connectable
            self.metadata = metadata or sqlalchemy.MetaData(bind=self.connectable)

            # Construct the fact table name:
            # If not specified explicitly, then it is:
            #       fact_prefix + name of the cube

            fact_prefix = fact_prefix or ""
            self.fact_name = cube.fact or fact_prefix + cube.name

            # Register the fact table immediately
            self.fact_key = self.cube.key or DEFAULT_KEY_FIELD

        # Mapper is responsible for finding corresponding physical columns to
        # dimension attributes and fact measures. It also provides information
        # about relevant joins to be able to retrieve certain attributes.

        self.mapper = Mapper(cube, cube.mappings, self.locale,
                                            schema=schema,
                                            fact_name=self.fact_name,
                                            dimension_prefix=dimension_prefix,
                                            joins=cube.joins)

        # StarQueryBuilder is creating SQL statements (using SQLAlchemy). It
        # also caches information about tables retrieved from metadata.

        self.query = StarQueryBuilder(self.cube, self.mapper,
                                      metadata=self.metadata)

    def fact(self, key_value):
        """Get a single fact with key `key_value` from cube."""

        key_column = self.query.fact_table.c[self.fact_key]
        condition = key_column == key_value
        select = self.query.denormalized_statement(whereclause=condition)

        if self.debug:
            self.logger.info("fact SQL:\n%s" % select)

        cursor = self.connectable.execute(select)
        row = cursor.fetchone()

        labels = [c.name for c in select.columns]

        if row:
            # Convert SQLAlchemy object into a dictionary
            record = dict(zip(labels, row))
        else:
            record = None

        cursor.close()

        return record

    def facts(self, cell, order=None, page=None, page_size=None):
        """Return all facts from `cell`, might be ordered and paginated."""

        # TODO: add ordering (ORDER BY)

        cond = self.query.condition_for_cell(cell)

        statement = self.query.denormalized_statement(whereclause=cond.condition)
        statement = paginated_statement(statement, page, page_size)
        statement = ordered_statement(statement, order, mapper=self.mapper, query=self.query)

        if self.debug:
            self.logger.info("facts SQL:\n%s" % statement)

        result = self.connectable.execute(statement)

        labels = [c.name for c in statement.columns]

        return ResultIterator(result, labels)

    def values(self, cell, dimension, depth=None, paths=None, hierarchy=None, 
                page=None, page_size=None, **options):
        """Return values for `dimension` with level depth `depth`. If `depth`
        is ``None``, all levels are returned.

        Number of database queries: 1.
        """
        dimension = self.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)

        levels = hierarchy.levels

        if depth == 0:
            raise ValueError("Depth for dimension values should not be 0")
        elif depth is not None:
            levels = levels[0:depth]

        # TODO: add ordering (ORDER BY)
        # TODO: this might unnecessarily add fact table as well, there might
        #       be cases where we do not want that (hm, might be? really? note
        #       the cell)

        attributes = []
        for level in levels:
            attributes.extend(level.attributes)

        cond = self.query.condition_for_cell(cell)
        statement = self.query.denormalized_statement(whereclause=cond.condition,
                                                        attributes=attributes)
        statement = paginated_statement(statement, page, page_size)
        statement = ordered_statement(statement, order, mapper=self.mapper, query=self.query)

        group_by = [self.query.column(attr) for attr in attributes]
        statement = statement.group_by(*group_by)

        if self.debug:
            self.logger.info("dimension values SQL:\n%s" % statement)

        result = self.connectable.execute(statement)
        labels = [c.name for c in statement.columns]

        return ResultIterator(result, labels)

    def aggregate(self, cell, measures=None, drilldown=None, attributes=None, 
                  page=None, page_size=None, order=None, **options):
        """Return aggregated result.

        Number of database queries:

        * without drill-down: 1 (summary)
        * with drill-down: 3 (summary, drilldown, total drill-down record
          count)
        """

        # TODO: add ordering (ORDER BY)
        if options.get("order_by"):
            self.logger.warn("ordering in aggregations is not yet implemented")

        # TODO: add documentation

        # Coalesce measures - make sure that they are Attribute objects, not
        # strings. Strings are converted to corresponding Cube measure
        # attributes
        if measures:
            measures = [self.cube.measure(measure) for measure in measures]

        result = AggregationResult()

        summary_statement = self.query.aggregation_statement(cell=cell,
                                                     measures=measures,
                                                     attributes=attributes)

        if self.debug:
            self.logger.info("aggregation SQL:\n%s" % summary_statement)

        cursor = self.connectable.execute(summary_statement)
        row = cursor.fetchone()

        if row:
            # Convert SQLAlchemy object into a dictionary
            labels = [c.name for c in summary_statement.columns]
            record = dict(zip(labels, row))
        else:
            record = None

        cursor.close()
        result.summary = record

        ##
        # Drill-down
        ##

        if drilldown:
            statement = self.query.aggregation_statement(cell=cell,
                                                         measures=measures,
                                                         attributes=attributes,
                                                         drilldown=drilldown)

            if self.debug:
                self.logger.info("aggregation drilldown SQL:\n%s" % statement)

            statement = paginated_statement(statement, page, page_size)
            statement = ordered_statement(statement, order, mapper=self.mapper, query=self.query)

            dd_result = self.connectable.execute(statement)
            labels = [c.name for c in statement.columns]

            result.drilldown = ResultIterator(dd_result, labels)

            # TODO: introduce option to disable this

            count_statement = statement.alias().count()
            row_count = self.connectable.execute(count_statement).fetchone()
            total_cell_count = row_count[0]
            result.total_cell_count = total_cell_count

        return result

    def validate(self):
        """Validate physical representation of model. Returns a list of
        dictionaries with keys: ``type``, ``issue``, ``object``.

        Types might be: ``join`` or ``attribute``.

        The ``join`` issues are:

        * ``no_table`` - there is no table for join
        * ``duplicity`` - either table or alias is specified more than once

        The ``attribute`` issues are:

        * ``no_table`` - there is no table for attribute
        * ``no_column`` - there is no column for attribute
        * ``duplicity`` - attribute is found more than once

        """
        issues = []

        # Check joins

        tables = set()
        aliases = set()
        alias_map = {}
        # 
        for join in self.mapper.joins:
            self.logger.debug("join: %s" % (join, ))

            if not join.master.column:
                issues.append(("join", "master column not specified", join))
            if not join.detail.table:
                issues.append(("join", "detail table not specified", join))
            elif join.detail.table == self.fact_name:
                issues.append(("join", "detail table should not be fact table", join))

            master_table = (join.master.schema, join.master.table)
            tables.add(master_table)

            detail_alias = (join.detail.schema, join.alias or join.detail.table)

            if detail_alias in aliases:
                issues.append(("join", "duplicate detail table %s" % detail_table, join))
            else:
                aliases.add(detail_alias)

            detail_table = (join.detail.schema, join.detail.table)
            alias_map[detail_alias] = detail_table

            if detail_table in tables and not join.alias:
                issues.append(("join", "duplicate detail table %s (no alias specified)" % detail_table, join))
            else:
                tables.add(detail_table)

        # Check for existence of joined tables:
        physical_tables = {}

        for table in tables:
            try:
                physical_table = sqlalchemy.Table(table[1], self.metadata,
                                        autoload=True,
                                        schema=table[0] or self.mapper.schema)
                physical_tables[(table[0] or self.mapper.schema, table[1])] = physical_table
            except sqlalchemy.exc.NoSuchTableError:
                issues.append(("join", "table %s.%s does not exist" % table, join))

        # Check attributes

        attributes = self.mapper.all_attributes()
        physical = self.mapper.map_attributes(attributes)

        for attr, ref in zip(attributes, physical):
            table_ref = (ref.schema, ref.table)
            table = physical_tables.get(table_ref)
            if table is None:
                issues.append(("attribute", "table %s.%s does not exist for attribute %s" % (table_ref[0], table_ref[1], self.mapper.logical(attr)), attr))
            else:
                try:
                    c = table.c[ref.column]
                except KeyError:
                    issues.append(("attribute", "column %s.%s.%s does not exist for attribute %s" % (table_ref[0], table_ref[1], ref.column, self.mapper.logical(attr)), attr))

        return issues

"""A Condition representation. `attributes` - list of attributes involved in the conditions,
`conditions` - SQL conditions, `group_by` - attributes to be grouped by."""
Condition = collections.namedtuple("Condition",
                                    ["attributes", "condition", "group_by"])

aggregation_functions = {
    "sum": sql.functions.sum,
    "min": sql.functions.min,
    "max": sql.functions.max,
    "count": sql.functions.count
}

# TODO: Rename StarQueryBuilder to QueryContext

class StarQueryBuilder(object):
    """StarQuery"""
    def __init__(self, cube, mapper, metadata, **options):
        """Object representing queries to the star. `mapper` is used for
        mapping logical to physical attributes and performing joins.
        `metadata` is a `sqlalchemy.MetaData` instance for getting physical
        table representations.

        Object attributes:

        * `fact_table` – the physical fact table - `sqlalchemy.Table` instance
        * `tables` – a dictionary where keys are table references (schema,
          table) or (shchema, alias) to real tables - `sqlalchemy.Table`
          instances

        .. note::

            To get results as a dictionary, you should ``zip()`` the returned
            rows after statement execution with:

                labels = [column.name for column in statement.columns]
                ...
                record = dict(zip(labels, row))

            This is little overhead for a workaround for SQLAlchemy behaviour
            in SQLite database. SQLite engine does not respect dots in column
            names which results in "duplicate column name" error.
        """
        super(StarQueryBuilder, self).__init__()

        self.logger = get_logger()

        self.cube = cube
        self.mapper = mapper
        self.schema = mapper.schema
        self.metadata = metadata

        # Prepare physical fact table - fetch from metadata
        #
        self.fact_name = mapper.fact_name
        self.fact_table = sqlalchemy.Table(self.fact_name, self.metadata,
                                           autoload=True, schema=self.schema)

        self.tables = {
                    (self.schema, self.fact_name): self.fact_table
                }

    def aggregation_statement(self, cell, measures=None,
                              attributes=None, drilldown=None):
        """Return a statement for summarized aggregation. `whereclause` is
        same as SQLAlchemy `whereclause` for
        `sqlalchemy.sql.expression.select()`. `attributes` is list of logical
        references to attributes to be selected. If it is ``None`` then all
        attributes are used."""

        # TODO: do not ignore attributes
        cell_cond = self.condition_for_cell(cell)
        attributes = cell_cond.attributes

        if drilldown:
            drilldown = coalesce_drilldown(cell, drilldown)
            for levels in drilldown.values():
                for level in levels:
                    attributes |= set(level.attributes)

        # TODO: add measures as well
        join_expression = self.join_expression_for_attributes(cell_cond.attributes)

        selection = []

        if measures is None:
            measures = self.cube.measures

        # Collect "columns" for measure aggregations
        for measure in measures:
            selection.extend(self.aggregations_for_measure(measure))

        # Added total record count
        # TODO: make this label configurable (should we?)
        # TODO: make presence of this configurable (shoud we?)
        rcount_label = "record_count"

        selection.append(sql.functions.count().label(rcount_label))

        group_by = None

        if drilldown:
            group_by = []
            for dim, levels in drilldown.items():
                for level in levels:
                    columns = [self.column(attr) for attr in level.attributes]
                    group_by.extend(columns)
                    selection.extend(columns)

        select = sql.expression.select(selection,
                                    whereclause=cell_cond.condition,
                                    from_obj=join_expression,
                                    use_labels=True,
                                    group_by=group_by)

        return select

    def aggregations_for_measure(self, measure):
        """Returns list of aggregation functions (sqlalchemy) on measure columns. 
        The result columns are labeled as `measure` + ``_`` = `aggregation`,
        for example: ``amount_sum`` or ``discount_min``.

        `measure` has to be `Attribute` instance.

        If measure has no explicit aggregations associated, then ``sum`` is
        assumed.
        """

        if not measure.aggregations:
            aggregations = ["sum"]
        else:
            aggregations = [agg.lower() for agg in measure.aggregations]

        result = []
        for agg_name in aggregations:
            if not agg_name in aggregation_functions:
                raise Exception("Unknown aggregation type %s for measure %s" % \
                                    (agg_name, measure))

            func = aggregation_functions[agg_name]
            label = "%s_%s" % (str(measure), agg_name)
            aggregation = func(self.column(measure)).label(label)
            result.append(aggregation)

        return result

    def denormalized_statement(self, whereclause=None, attributes=None):
        """Return a statement (see class description for more information) for
        denormalized view. `whereclause` is same as SQLAlchemy `whereclause`
        for `sqlalchemy.sql.expression.select()`. `attributes` is list of
        logical references to attributes to be selected. If it is ``None`` then
        all attributes are used."""

        if attributes is None:
            attributes = self.mapper.all_attributes()

        join_expression = self.join_expression_for_attributes(attributes)

        columns = [self.column(attr) for attr in attributes]

        select = sql.expression.select(columns,
                                    whereclause=whereclause,
                                    from_obj=join_expression,
                                    use_labels=True)

        return select


    def join_expression_for_attributes(self, attributes):
        """Returns a join expression for `attributes`"""
        physical_references = self.mapper.map_attributes(attributes)
        joins = self.mapper.relevant_joins(physical_references)
        return self.join_expression(joins)

    def join_expression(self, joins):
        """Create partial expression on a fact table with `joins` that can be
        used as core for a SELECT statement. `join` is a list of joins
        returned from mapper (most probably by `Mapper.relevant_joins()`)
        """

        self.logger.debug("create basic expression with %d joins" % len(joins))

        expression = self.fact_table

        for join in joins:
            # self.logger.debug("join detail: %s" % (join.detail, ))

            if not join.detail.table or join.detail.table == self.fact_name:
                raise ValueError("Detail table name should be present and should not be a fact table.")

            master_table = self.table(join.master.schema, join.master.table)
            detail_table = self.table(join.detail.schema, join.detail.table, join.alias)

            try:
                master_column = master_table.c[join.master.column]
            except:
                raise Exception('Unable to find master key (schema %s) "%s"."%s" ' \
                                    % join.master)
            try:
                detail_column = detail_table.c[join.detail.column]
            except:
                raise Exception('Unable to find detail key (schema %s) "%s"."%s" ' \
                                    % join.detail)

            onclause = master_column == detail_column

            expression = sql.expression.join(expression,
                                                    detail_table,
                                                    onclause=onclause)
        return expression

    def condition_for_cell(self, cell):
        """Constructs conditions for all cuts in the `cell`. Returns a named
        tuple with keys:

        * ``condition`` - SQL conditions
        * ``attributes`` - attributes that are involved in the conditions.
          This should be used for join construction.
        * ``group_by`` - attributes used for GROUP BY expression
        """

        if not cell:
            return Condition([], None, [])

        attributes = set()
        conditions = []
        group_by = []

        for cut in cell.cuts:
            dim = self.cube.dimension(cut.dimension)

            if isinstance(cut, PointCut):
                path = cut.path
                wrapped_cond = self.condition_for_point(dim, path)

                condition = wrapped_cond.condition
                attributes |= wrapped_cond.attributes
                group_by += wrapped_cond.group_by

            elif isinstance(cut, SetCut):
                conditions = []

                for path in cut.paths:
                    wrapped_cond = self.condition_for_point(dim, path)
                    conditions.append(wrapped_cond.condition)
                    attributes |= wrapped_cond.attributes
                    group_by += wrapped_cond.group_by

                condition = sql.expression.or_(*conditions)

            elif isinstance(cut, RangeCut):
                raise NotImplementedError("Condition for range cuts is not yet implemented")

            else:
                raise Exception("Only point and set cuts are supported in SQL browser at the moment")

            conditions.append(condition)

        condition = sql.expression.and_(*conditions)

        return Condition(attributes, condition, group_by)

    def condition_for_point(self, dim, path, hierarchy=None):
        """Returns a `Condition` tuple (`attributes`, `conditions`,
        `group_by`) dimension `dim` point at `path`. It is a compound
        condition - one equality condition for each path element in form:
        ``level[i].key = path[i]``"""

        # TODO: add support for possible multiple hierarchies

        attributes = set()
        conditions = []
        group_by = []

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise Exception("Path has more items (%d: %s) than there are levels (%d) "
                            "in dimension %s" % (len(path), path, len(levels), dim.name))

        level = None
        for level, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level.key)
            conditions.append(column == value)

            # FIXME: join attributes only if details are requested
            # Collect grouping columns
            for attr in level.attributes:
                column = self.column(attr)
                group_by.append(column)
                attributes.add(attr)

        condition = sql.expression.and_(*conditions)

        return Condition(attributes,condition,group_by)

    def table(self, schema, table_name, alias=None):
        """Return a SQLAlchemy Table instance. If table was already accessed,
        then existing table is returned. Otherwise new instance is created.

        If `schema` is ``None`` then browser's schema is used. If `table_name`
        is ``None``, then fact table is used.
        """

        # table_name = table_name or self.fact_name
        aliased_name = alias or table_name
        table_ref = (schema or self.schema, aliased_name)
        if table_ref in self.tables:
            return self.tables[table_ref]

        table = sqlalchemy.Table(table_name, self.metadata,
                                 autoload=True, schema=schema)

        self.logger.debug("registering table '%s' as '%s'" % (table_name, aliased_name))
        if alias:
            table = table.alias(alias)

        self.tables[table_ref] = table
        return table

    def column(self, attribute):
        """Return a column object for attribute"""

        ref = self.mapper.physical(attribute)
        table = self.table(ref.schema, ref.table)

        column = table.c[ref.column]
        column = column.label(self.mapper.logical(attribute))

        return column

def coalesce_drilldown(cell, drilldown):
    """Returns a dictionary where keys are dimensions and values are list of
    levels to be drilled down. `drilldown` should be a list of dimensions (or
    dimension names) or a dictionary where keys are dimension names and values
    are level names to drill up to.

    For the list of dimensions or if the level is not specified, then up to
    the next level in the cell is considered.
    """

    # TODO: consider hierarchies (currently ignored, default is used)

    result = {}

    depths = cell.level_depths()

    if type(drilldown) == list or type(drilldown) == tuple:

        for dim in drilldown:
            dim = cell.cube.dimension(dim)
            depth = depths.get(str(dim)) or 0
            result[dim.name] = drilldown_levels(dim, depth+1)

    elif isinstance(drilldown, dict):

        for dim, level in drilldown.items():
            dim = cell.cube.dimension(dim)

            if level:
                hier = dim.default_hierarchy
                index = hier.level_index(level)
                result[dim.name] = hier[:index+1]
            else:
                depth = depths.get(str(dim)) or 0
                result[dim.name] = drilldown_levels(dim, depth+1)

    elif drilldown is not None:
        raise TypeError("Drilldown is of unknown type: %s" % type(drilldown))

    return result


def drilldown_levels(dimension, depth, hierarchy=None):
    """Get drilldown levels up to level at `depth`. If depth is ``None``
    returns first level only. `dimension` has to be `Dimension` instance. """

    hier = dimension.hierarchy(hierarchy)
    depth = depth or 0

    if depth > len(hier):
        raise ValueError("Hierarchy %s in dimension %s has only %d levels, "
                         "can not drill to %d" % \
                         (hier,dimension,len(hier),depth+1))

    return hier[:depth]

def paginated_statement(statement, page, page_size):
    """Returns paginated statement if page is provided, otherwise returns
    the same statement."""

    if page is not None and page_size is not None:
        return statement.offset(page * page_size).limit(page_size)
    else:
        return statement

def ordered_statement(statement, order, mapper, query):
    """Returns a SQL statement which is ordered according to the `order`. If
    the statement contains attributes that have natural order specified, then
    the natural order is used, if not overriden in the `order`."""

    # Each attribute mentioned in the order should be present in the selection
    # or as some column from joined table. Here we get the list of already
    # selected columns and derived aggregates

    selection = dict(statement.columns)

    # Make sure that the `order` is a list of of tuples (`attribute`,
    # `order`). If element of the `order` list is a string, then it is
    # converted to (`string`, ``None``).

    order = order or []
    order_by = collections.OrderedDict()

    for item in order:
        if isinstance(item, basestring):
            try:
                attribute = mapper.attribute(item)
                column = query.column(attribute)
            except KeyError:
                column = selection[item]

            order_by[item] = column
        else:
            # item is a two-element tuple where first element is attribute
            # name and second element is ordering
            try:
                attribute = mapper.attribute(item[0])
                column = query.column(attribute)
            except KeyError:
                column = selection[item[0]]
            order_by[item] = order_column(column, item[1])

    # Collect natural order for selected columns

    # TODO: should we add natural order for columns that are not selected
    #       but somewhat involved in the process (GROUP BY)?

    for (name, column) in selection.items():
        try:
            # Backward mapping: get Attribute instance by name. The column
            # name used here is already labelled to the logical name
            attribute = mapper.attribute(name)
        except KeyError:
            # Since we are already selecting the column, then it should exist
            # this exception is raised when we are trying to get Attribute
            # object for an aggregate - we can safely ignore this.

            # TODO: add natural ordering for measures (may be nice)
            attribute = None

        if attribute and attribute.order and name not in ordering:
            order_by[name] = order_column(column, attribute.order)

    return statement.order_by(*order_by.values())


def order_column(column, order):
    """Orders a `column` according to `order` specified as string."""

    if not order:
        return column
    elif order.lower().startswith("asc"):
        return column.asc()
    elif order.lower().startswith("desc"):
        return column.desc()
    else:
        raise Exception("Unknown order %s for column %s") % (order, column)


class ResultIterator(object):
    """
    Iterator that returns SQLAlchemy ResultProxy rows as dictionaries
    """
    def __init__(self, result, labels):
        self.result = result
        self.batch = None
        self.labels = labels

    def __iter__(self):
        return self

    def next(self):
        if not self.batch:
            many = self.result.fetchmany()
            if not many:
                raise StopIteration
            self.batch = collections.deque(many)

        row = self.batch.popleft()

        return dict(zip(self.labels, row))

####
# Backend related functions
###

def ddl_for_model(url, model, fact_prefix=None, dimension_prefix=None, schema_type=None):
    """Create a star schema DDL for a model.

    Parameters:

    * `url` - database url – no connection will be created, just used by
       SQLAlchemy to determine appropriate engine backend
    * `cube` - cube to be described
    * `dimension_prefix` - prefix used for dimension tables
    * `schema_type` - ``logical``, ``physical``, ``denormalized``

    As model has no data storage type information, following simple rule is
    used:

    * fact ID is an integer
    * all keys are strings
    * all attributes are strings
    * all measures are floats

    .. warning::

        Does not respect localized models yet.

    """
    raise NotImplementedError

def create_workspace(model, config):
    """Create workspace for `model` with configuration in dictionary `config`. 
    This method is used by the slicer server."""

    try:
        dburl = config["url"]
    except KeyError:
        raise Exception("No URL specified in configuration")

    schema = config.get("schema")
    dimension_prefix = config.get("dimension_prefix")
    fact_prefix = config.get("fact_prefix")

    engine = sqlalchemy.create_engine(dburl)

    workspace = SQLStarWorkspace(model, engine, schema,
                                    dimension_prefix = dimension_prefix,
                                    fact_prefix = fact_prefix)

    return workspace

class SQLStarWorkspace(object):
    """Factory for browsers"""
    def __init__(self, model, engine, schema=None, dimension_prefix=None,
                 fact_prefix=None):
        """Create a workspace"""
        super(SQLStarWorkspace, self).__init__()
        self.model = model
        self.engine = engine
        self.metadata = sqlalchemy.MetaData(bind = self.engine)
        self.dimension_prefix = dimension_prefix
        self.fact_prefix = fact_prefix
        self.schema = schema

    def browser_for_cube(self, cube, locale=None):
        """Creates, configures and returns a browser for a cube"""

        # TODO(Stiivi): make sure that we are leaking connections here
        cube = self.model.cube(cube)
        browser = StarBrowser(cube, self.engine, locale=locale,
                                dimension_prefix=self.dimension_prefix,
                                fact_prefix=self.fact_prefix,
                                schema=self.schema,
                                metadata=self.metadata)
        return browser

    def validate_model(self):
        """Validate physical representation of model. Returns a list of 
        dictionaries with keys: ``type``, ``issue``, ``object``.

        Types might be: ``join`` or ``attribute``.

        The ``join`` issues are:

        * ``no_table`` - there is no table for join
        * ``duplicity`` - either table or alias is specified more than once

        The ``attribute`` issues are:

        * ``no_table`` - there is no table for attribute
        * ``no_column`` - there is no column for attribute
        * ``duplicity`` - attribute is found more than once

        """
        issues = []

        for cube in self.model.cubes:
            browser = self.browser_for_cube(cube)
            issues += browser.validate()

        return issues
