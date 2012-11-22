# -*- coding=utf -*-
# Actually, this is a furry snowflake, not a nice star

from cubes.browser import *
from cubes.common import get_logger
from cubes.mapper import SnowflakeMapper, DenormalizedMapper
from cubes.mapper import DEFAULT_KEY_FIELD
import logging
import collections
from cubes.errors import *
from cubes.computation import *

try:
    import sqlalchemy
    import sqlalchemy.sql as sql

    aggregation_functions = {
        "sum": sql.functions.sum,
        "min": sql.functions.min,
        "max": sql.functions.max,
        "count": sql.functions.count
    }

except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")
    aggregation_functions = {}

__all__ = [
    "SnowflakeBrowser",
    "QueryContext"
]

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

# Browsing context:
#     * engine
#     * metadata
#
#     * locale
#
#     * fact name
#     * dimension table prefix
#     * schema

class SnowflakeBrowser(AggregationBrowser):
    """docstring for SnowflakeBrowser"""

    def __init__(self, cube, connectable=None, locale=None, metadata=None,
                 debug=False, **options):
        """SnowflakeBrowser is a SQL-based AggregationBrowser implementation that
        can aggregate star and snowflake schemas without need of having
        explicit view or physical denormalized table.

        Attributes:

        * `cube` - browsed cube
        * `connectable` - SQLAlchemy connectable object (engine or connection)
        * `locale` - locale used for browsing
        * `metadata` - SQLAlchemy MetaData object
        * `debug` - output SQL to the logger at INFO level
        * `options` - passed to the mapper and context (see their respective
          documentation)

        **Limitations:**

        * only one locale can be used for browsing at a time
        * locale is implemented as denormalized: one column for each language
        """
        super(SnowflakeBrowser, self).__init__(cube)

        if cube == None:
            raise ArgumentError("Cube for browser should not be None.")

        self.logger = get_logger()

        self.cube = cube
        self.locale = locale or cube.model.locale
        self.debug = debug

        if connectable is not None:
            self.connectable = connectable
            self.metadata = metadata or sqlalchemy.MetaData(bind=self.connectable)

        # Mapper is responsible for finding corresponding physical columns to
        # dimension attributes and fact measures. It also provides information
        # about relevant joins to be able to retrieve certain attributes.

        if options.get("use_denormalization"):
            mapper_class = DenormalizedMapper
        else:
            mapper_class = SnowflakeMapper

        self.logger.debug("using mapper %s for cube '%s' (locale: %s)" % \
                            (str(mapper_class.__name__), cube.name, locale))

        self.mapper = mapper_class(cube, locale=self.locale, **options)
        self.logger.debug("mapper schema: %s" % self.mapper.schema)

        # QueryContext is creating SQL statements (using SQLAlchemy). It
        # also caches information about tables retrieved from metadata.

        self.context = QueryContext(self.cube, self.mapper,
                                      metadata=self.metadata)

    def fact(self, key_value):
        """Get a single fact with key `key_value` from cube."""

        select = self.context.fact_statement(key_value)

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

        statement = self.context.denormalized_statement()
        cond = self.context.condition_for_cell(cell)

        if cond.condition is not None:
            statement = statement.where(cond.condition)

        statement = paginated_statement(statement, page, page_size)
        statement = ordered_statement(statement, order, context=self.context)

        if self.debug:
            self.logger.info("facts SQL:\n%s" % statement)

        result = self.connectable.execute(statement)

        labels = [c.name for c in statement.columns]

        return ResultIterator(result, labels)

    def values(self, cell, dimension, depth=None, paths=None, hierarchy=None, 
                page=None, page_size=None, order=None, **options):
        """Return values for `dimension` with level depth `depth`. If `depth`
        is ``None``, all levels are returned.

        Number of database queries: 1.
        """
        dimension = self.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)

        levels = hierarchy.levels

        if depth == 0:
            raise ArgumentError("Depth for dimension values should not be 0")
        elif depth is not None:
            levels = levels[0:depth]

        # TODO: add ordering (ORDER BY)
        # TODO: this might unnecessarily add fact table as well, there might
        #       be cases where we do not want that (hm, might be? really? note
        #       the cell)

        attributes = []
        for level in levels:
            attributes.extend(level.attributes)

        statement = self.context.denormalized_statement(attributes=attributes,
                                                        include_fact_key=False)
        cond = self.context.condition_for_cell(cell)

        if cond.condition is not None:
            statement = statement.where(cond.condition)
        statement = paginated_statement(statement, page, page_size)
        statement = ordered_statement(statement, order, context=self.context)

        group_by = [self.context.column(attr) for attr in attributes]
        statement = statement.group_by(*group_by)

        if self.debug:
            self.logger.info("dimension values SQL:\n%s" % statement)

        result = self.connectable.execute(statement)
        labels = [c.name for c in statement.columns]

        return ResultIterator(result, labels)

    def aggregate(self, cell=None, measures=None, drilldown=None,
                  attributes=None, page=None, page_size=None, order=None,
                  **options):
        """Return aggregated result.

        Number of database queries:

        * without drill-down: 1 (summary)
        * with drill-down: 3 (summary, drilldown, total drill-down record
          count)
        """

        if not cell:
            cell = Cell(self.cube)

        # TODO: add documentation

        # Coalesce measures - make sure that they are Attribute objects, not
        # strings. Strings are converted to corresponding Cube measure
        # attributes
        if measures:
            measures = [self.cube.measure(measure) for measure in measures]

        result = AggregationResult()
        result.cell = cell
        result.measures = measures

        summary_statement = self.context.aggregation_statement(cell=cell,
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
            drilldown = coalesce_drilldown(cell, drilldown)
            result.levels = drilldown
            statement = self.context.aggregation_statement(cell=cell,
                                                         measures=measures,
                                                         attributes=attributes,
                                                         drilldown=drilldown)

            if self.debug:
                self.logger.info("aggregation drilldown SQL:\n%s" % statement)

            statement = paginated_statement(statement, page, page_size)
            statement = ordered_statement(statement, order, context=self.context)

            dd_result = self.connectable.execute(statement)
            labels = [c.name for c in statement.columns]

            result.cells = ResultIterator(dd_result, labels)

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
            elif join.detail.table == self.mapper.fact_name:
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
`conditions` - SQL conditions"""
Condition = collections.namedtuple("Condition",
                                    ["attributes", "condition"])

"""Aliased table information"""
AliasedTable = collections.namedtuple("AliasedTable",
                                    ["schema", "table", "alias"])

class QueryContext(object):

    def __init__(self, cube, mapper, metadata, **options):
        """Object providing context for constructing queries. Puts together
        the mapper and physical structure. `mapper` - which is used for
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
        super(QueryContext, self).__init__()

        self.logger = get_logger()

        self.cube = cube
        self.mapper = mapper
        self.schema = mapper.schema
        self.metadata = metadata

        # Prepare physical fact table - fetch from metadata
        #
        self.fact_key = self.cube.key or DEFAULT_KEY_FIELD
        self.fact_name = mapper.fact_name
        self.fact_table = sqlalchemy.Table(self.fact_name, self.metadata,
                                           autoload=True, schema=self.schema)

        self.tables = {
                    (self.schema, self.fact_name): self.fact_table
                }

        # Collect all tables and their aliases.
        # FIXME: this should be cached per-browser/cube instance

        # table_aliases contains mapping between aliased table name and real
        # table name with alias:
        # 
        #       (schema, aliased_name) --> (schema, real_name, alias)
        #
        self.table_aliases = {
            (self.schema, self.fact_name): (self.schema, self.fact_name, None)
        }

        # Collect all table aliases from joins detail tables
        for join in self.mapper.joins:
            # just ask for the table
            table = AliasedTable(join.detail.schema,
                                 join.detail.table,
                                 join.alias)
            table_alias = (join.detail.schema, join.alias or join.detail.table)
            self.table_aliases[table_alias] = table

    def aggregation_statement(self, cell, measures=None,
                              attributes=None, drilldown=None):
        """Return a statement for summarized aggregation. `whereclause` is
        same as SQLAlchemy `whereclause` for
        `sqlalchemy.sql.expression.select()`. `attributes` is list of logical
        references to attributes to be selected. If it is ``None`` then all
        attributes are used. `drilldown` has to be a dictionary. Use
        `coalesce_drilldown()` to prepare correct drill-down statement."""

        cell_cond = self.condition_for_cell(cell)

        if not attributes:
            attributes = set()

            if drilldown:
                for levels in drilldown.values():
                    for level in levels:
                        attributes |= set(level.attributes)

        attributes = set(attributes) | set(cell_cond.attributes)

        join_expression = self.join_expression_for_attributes(attributes)

        # TODO: add measures as well
        selection = []

        group_by = None
        if drilldown:
            group_by = []
            for dim, levels in drilldown.items():
                for level in levels:
                    columns = [self.column(attr) for attr in level.attributes
                                                        if attr in attributes]
                    group_by.extend(columns)
                    selection.extend(columns)

        # Measures
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

        select = sql.expression.select(selection,
                                    from_obj=join_expression,
                                    use_labels=True,
                                    group_by=group_by)

        if cell_cond.condition is not None:
            select = select.where(cell_cond.condition)

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
                raise ArgumentError("Unknown aggregation type %s for measure %s" % \
                                    (agg_name, measure))

            func = aggregation_functions[agg_name]
            label = "%s_%s" % (str(measure), agg_name)
            aggregation = func(self.column(measure)).label(label)
            result.append(aggregation)

        return result

    def denormalized_statement(self, attributes=None, expand_locales=False,
                               include_fact_key=True):
        """Return a statement (see class description for more information) for
        denormalized view. `whereclause` is same as SQLAlchemy `whereclause`
        for `sqlalchemy.sql.expression.select()`. `attributes` is list of
        logical references to attributes to be selected. If it is ``None`` then
        all attributes are used.

        Set `expand_locales` to ``True`` to expand all localized attributes.
        """

        if attributes is None:
            attributes = self.mapper.all_attributes()

        join_expression = self.join_expression_for_attributes(attributes, expand_locales=expand_locales)

        columns = self.columns(attributes, expand_locales=expand_locales)

        if include_fact_key:
            key_column = self.fact_table.c[self.fact_key].label(self.fact_key)
            columns.insert(0, key_column)

        select = sql.expression.select(columns,
                                    from_obj=join_expression,
                                    use_labels=True)

        return select

    def fact_statement(self, key_value):
        """Return a statement for selecting a single fact based on `key_value`"""

        key_column = self.fact_table.c[self.fact_key]
        condition = key_column == key_value
        statement = self.denormalized_statement()

        if condition is not None:
            statement = statement.where(condition)

        return statement


    def join_expression_for_attributes(self, attributes, expand_locales=False):
        """Returns a join expression for `attributes`"""
        physical_references = self.mapper.map_attributes(attributes, expand_locales=expand_locales)

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
                raise MappingError("Detail table name should be present and should not be a fact table.")

            master_table = self.table(join.master.schema, join.master.table)
            detail_table = self.table(join.detail.schema, join.alias or join.detail.table)

            try:
                master_column = master_table.c[join.master.column]
            except:
                raise MappingError('Unable to find master key (schema %s) "%s"."%s" ' \
                                    % join.master[0:3])
            try:
                detail_column = detail_table.c[join.detail.column]
            except:
                raise MappingError('Unable to find detail key (schema %s) "%s"."%s" ' \
                                    % join.detail[0:3])

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
            return Condition([], None)

        attributes = set()
        conditions = []

        for cut in cell.cuts:
            dim = self.cube.dimension(cut.dimension)

            if isinstance(cut, PointCut):
                path = cut.path
                wrapped_cond = self.condition_for_point(dim, path)

                condition = wrapped_cond.condition
                attributes |= wrapped_cond.attributes

            elif isinstance(cut, SetCut):
                set_conds = []

                for path in cut.paths:
                    wrapped_cond = self.condition_for_point(dim, path)
                    set_conds.append(wrapped_cond.condition)
                    attributes |= wrapped_cond.attributes

                condition = sql.expression.or_(*set_conds)

            elif isinstance(cut, RangeCut):
                # FIXME: use hierarchy
                range_cond = self.range_condition(cut.dimension, None, cut.from_path, cut.to_path)
                condition = range_cond.condition
                attributes |= range_cond.attributes

            else:
                raise ArgumentError("Unknown cut type %s" % type(cut))

            conditions.append(condition)

        condition = sql.expression.and_(*conditions)
        return Condition(attributes, condition)

    def condition_for_point(self, dim, path, hierarchy=None):
        """Returns a `Condition` tuple (`attributes`, `conditions`,
        `group_by`) dimension `dim` point at `path`. It is a compound
        condition - one equality condition for each path element in form:
        ``level[i].key = path[i]``"""

        attributes = set()
        conditions = []

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise ArgumentError("Path has more items (%d: %s) than there are levels (%d) "
                                "in dimension %s" % (len(path), path, len(levels), dim.name))

        for level, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level.key)
            conditions.append(column == value)

            # FIXME: join attributes only if details are requested
            # Collect grouping columns
            for attr in level.attributes:
                attributes.add(attr)

        condition = sql.expression.and_(*conditions)

        return Condition(attributes,condition)

    def range_condition(self, dim, hierarchy, from_path, to_path):
        """Return a condition for a hierarchical range (`from_path`,
        `to_path`). Return value is a `Condition` tuple."""

        dim = self.cube.dimension(dim)

        lower = self.boundary_condition(dim, hierarchy, from_path, 0)
        upper = self.boundary_condition(dim, hierarchy, to_path, 1)

        if from_path and not to_path:
            return lower
        elif not from_path and to_path:
            return upper
        else:
            attributes = lower.attributes | upper.attributes
            condition = sql.expression.and_(lower.condition, upper.condition)
            return Condition(attributes, condition)

    def boundary_condition(self, dim, hierarchy, path, bound, first=None):
        """Return a `Condition` tuple for a boundary condition. If `bound` is
        1 then path is considered to be upper bound (operators < and <= are
        used), otherwise path is considered as lower bound (operators > and >=
        are used )"""

        if first is None:
            return self.boundary_condition(dim, hierarchy, path, bound, first=True)

        if not path:
            return Condition(set(), None)

        last = self.boundary_condition(dim, hierarchy, path[:-1], bound, first=False)

        levels = dim.hierarchy(hierarchy).levels_for_path(path)

        if len(path) > len(levels):
            raise ArgumentError("Path has more items (%d: %s) than there are levels (%d) "
                                "in dimension %s" % (len(path), path, len(levels), dim.name))

        attributes = set()
        conditions = []

        for level, value in zip(levels[:-1], path[:-1]):
            column = self.column(level.key)
            conditions.append(column == value)

            for attr in level.attributes:
                attributes.add(attr)

        # Select required operator according to bound
        # 0 - lower bound
        # 1 - upper bound
        if bound == 1:
            # 1 - upper bound (that is <= and < operator)
            operator = sql.operators.le if first else sql.operators.lt
        else:
            # else - lower bound (that is >= and > operator)
            operator = sql.operators.ge if first else sql.operators.gt

        column = self.column(levels[-1].key)
        conditions.append( operator(column, path[-1]) )

        for attr in levels[-1].attributes:
            attributes.add(attr)

        condition = sql.expression.and_(*conditions)
        attributes |= last.attributes

        if last.condition is not None:
            condition = sql.expression.or_(condition, last.condition)

        return Condition(attributes, condition)

    def table(self, schema, table_name):
        """Return a SQLAlchemy Table instance. If table was already accessed,
        then existing table is returned. Otherwise new instance is created.

        If `schema` is ``None`` then browser's default schema is used.
        """

        aliased_ref = (schema or self.schema, table_name)

        if aliased_ref in self.tables:
            return self.tables[aliased_ref]

        # Get real table reference
        table_ref = self.table_aliases[aliased_ref]

        table = sqlalchemy.Table(table_ref.table, self.metadata,
                                 autoload=True, schema=table_ref.schema)

        self.logger.debug("registering table '%s' as '%s'" % (table_ref.table,
                                                                table_name))
        if table_ref.alias:
            table = table.alias(table_ref.alias)

        self.tables[aliased_ref] = table

        return table

    def column(self, attribute, locale=None):
        """Return a column object for attribute. `locale` is explicit locale
        to be used. If not specified, then the current browsing/mapping locale
        is used for localizable attributes."""

        ref = self.mapper.physical(attribute, locale)
        table = self.table(ref.schema, ref.table)
        column = table.c[ref.column]

        # Extract part of the date
        if ref.extract:
            column = sql.expression.extract(ref.extract, column)

        column = column.label(self.mapper.logical(attribute, locale))

        return column

    def columns(self, attributes, expand_locales=False):
        """Returns list of columns.If `expand_locales` is True, then one
        column per attribute locale is added."""

        if expand_locales:
            columns = []
            for attr in attributes:
                if attr.locales:
                    columns += [self.column(attr, locale) for locale in attr.locales]
                else: # if not attr.locales
                    columns.append(self.column(attr))
        else:
            columns = [self.column(attr) for attr in attributes]

        return columns

class AggregatedCubeBrowser(AggregationBrowser):
    """docstring for SnowflakeBrowser"""

    def __init__(self, cube, connectable=None, locale=None, metadata=None,
                 debug=False, **options):
        """AggregatedCubeBrowser is a SQL-based AggregationBrowser
        implementation that uses pre-aggregated table.

        Attributes:

        * `cube` - browsed cube
        * `connectable` - SQLAlchemy connectable object (engine or connection)
        * `locale` - locale used for browsing
        * `metadata` - SQLAlchemy MetaData object
        * `debug` - output SQL to the logger at INFO level
        * `options` - passed to the mapper and context (see their respective
          documentation)

        """
        super(AggregatedCubeBrowser, self).__init__(cube)

        if cube == None:
            raise ArgumentError("Cube for browser should not be None.")

        self.logger = get_logger()

        self.cube = cube
        self.locale = locale or cube.model.locale
        self.debug = debug

        if connectable is not None:
            self.connectable = connectable
            self.metadata = metadata or sqlalchemy.MetaData(bind=self.connectable)

        # Mapper is responsible for finding corresponding physical columns to
        # dimension attributes and fact measures. It also provides information
        # about relevant joins to be able to retrieve certain attributes.

        if options.get("use_denormalization"):
            mapper_class = DenormalizedMapper
        else:
            mapper_class = SnowflakeMapper

        self.logger.debug("using mapper %s for cube '%s' (locale: %s)" % \
                            (str(mapper_class.__name__), cube.name, locale))

        self.mapper = mapper_class(cube, locale=self.locale, **options)
        self.logger.debug("mapper schema: %s" % self.mapper.schema)

        # QueryContext is creating SQL statements (using SQLAlchemy). It
        # also caches information about tables retrieved from metadata.

        self.context = QueryContext(self.cube, self.mapper,
                                      metadata=self.metadata)

def paginated_statement(statement, page, page_size):
    """Returns paginated statement if page is provided, otherwise returns
    the same statement."""

    if page is not None and page_size is not None:
        return statement.offset(page * page_size).limit(page_size)
    else:
        return statement

def ordered_statement(statement, order, context):
    """Returns a SQL statement which is ordered according to the `order`. If
    the statement contains attributes that have natural order specified, then
    the natural order is used, if not overriden in the `order`."""

    # Each attribute mentioned in the order should be present in the selection
    # or as some column from joined table. Here we get the list of already
    # selected columns and derived aggregates

    selection = collections.OrderedDict()
    for c in statement.columns:
        selection[str(c)] = c

    # Make sure that the `order` is a list of of tuples (`attribute`,
    # `order`). If element of the `order` list is a string, then it is
    # converted to (`string`, ``None``).

    order = order or []
    order_by = collections.OrderedDict()

    for item in order:
        if isinstance(item, basestring):
            try:
                attribute = context.mapper.attribute(item)
                column = context.column(attribute)
            except KeyError:
                column = selection[item]

            order_by[item] = column
        else:
            # item is a two-element tuple where first element is attribute
            # name and second element is ordering
            try:
                attribute = context.mapper.attribute(item[0])
                column = context.column(attribute)
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
            attribute = context.mapper.attribute(name)
        except KeyError:
            # Since we are already selecting the column, then it should exist
            # this exception is raised when we are trying to get Attribute
            # object for an aggregate - we can safely ignore this.

            # TODO: add natural ordering for measures (may be nice)
            attribute = None

        if attribute and attribute.order and name not in order_by.keys():
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
        raise ArgumentError("Unknown order %s for column %s") % (order, column)


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

