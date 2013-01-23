# -*- coding: utf-8 -*-
"""Logical to Physical Mappers"""

import collections
from cubes.common import get_logger
from cubes.errors import *

__all__ = (
    "Mapper",
    "SnowflakeMapper",
    "DenormalizedMapper",
    "TableColumnReference",
    "TableJoin",
    "coalesce_physical",
    "DEFAULT_KEY_FIELD"
)

DEFAULT_KEY_FIELD = "id"

"""Physical reference to a table column. Note that the table might be an
aliased table name as specified in relevant join."""
TableColumnReference = collections.namedtuple("TableColumnReference",
                                    ["schema", "table", "column", "extract"])

"""Table join specification. `master` and `detail` are TableColumnReference
(3-item) tuples"""
TableJoin = collections.namedtuple("TableJoin",
                                    ["master", "detail", "alias"])

def coalesce_physical(ref, default_table=None, schema=None):
    """Coalesce physical reference `ref` which might be:

    * a string in form ``"table.column"``
    * a list in form ``(table, column)``
    * a list in form ``(schema, table, column)``
    * a dictionary with keys: ``schema``, ``table``, ``column`` where
      ``column`` is required, the rest are optional

    Returns tuple (`schema`, `table`, `column`, `extract`), which is a named
    tuple `TableColumnReference`.

    If no table is specified in reference and `default_table` is not
    ``None``, then `default_table` will be used.

    .. note::

        The `table` element might be a table alias specified in list of joins.

    """

    if isinstance(ref, basestring):
        split = ref.split(".")

        if len(split) > 1:
            dim_name = split[0]
            attr_name = ".".join(split[1:])
            return TableColumnReference(schema, dim_name, attr_name, None)
        else:
            return TableColumnReference(schema, default_table, ref, None)
    elif isinstance(ref, dict):
        return TableColumnReference(ref.get("schema", schema),
                                 ref.get("table", default_table),
                                 ref.get("column"),
                                 ref.get("extract"))
    else:
        if len(ref) == 2:
            return TableColumnReference(schema, ref[0], ref[1], None)
        elif len(ref) == 3:
            return TableColumnReference(ref[0], ref[1], ref[2], None)
        else:
            raise BackendError("Number of items in table reference should "\
                               "be 2 (table, column) or 3 (schema, table, column)")


class Mapper(object):
    """Mapper is core clas for translating logical model to physical
    database schema.
    """
    # WARNING: do not put any SQL/engine/connection related stuff into this
    # class yet. It might be moved to the cubes as one of top-level modules
    # and subclassed here.

    def __init__(self, cube, locale=None, schema=None, fact_name=None,
                 **options):
        """Abstract class for mappers which maps logical references to
        physical references (tables and columns).

        Attributes:

        * `cube` - mapped cube
        * `simplify_dimension_references` – references for flat dimensions
          (with one level and no details) will be just dimension names, no
          attribute name. Might be useful when using single-table schema, for
          example, with couple of one-column dimensions.
        * `fact_name` – fact name, if not specified then `cube.name` is used
        * `schema` – default database schema

        """

        super(Mapper, self).__init__()

        if cube == None:
            raise Exception("Cube for mapper should not be None.")

        self.logger = get_logger()

        self.cube = cube
        self.locale = locale

        fact_prefix = options.get("fact_prefix") or ""
        self.fact_name = fact_name or self.cube.fact or fact_prefix+self.cube.name
        self.schema=schema

        if "simplify_dimension_references" in options:
            self.simplify_dimension_references = options["simplify_dimension_references"]
        else:
            self.simplify_dimension_references = True

        if self.schema:
            schemastr = "'%s'" % self.schema
        else:
            schemastr = "(default)"

        self.logger.debug("mapper options: fact:'%s', schema:%s, "
                          "simplify: %s" % (self.fact_name, schemastr,
                                            self.simplify_dimension_references))

        self._collect_attributes()

    def _collect_attributes(self):
        """Collect all cube attributes and create a dictionary where keys are
        logical references and values are `cubes.model.Attribute` objects.
        This method should be used after each cube or mappings change.
        """

        self.attributes = collections.OrderedDict()

        for attr in self.cube.measures:
            self.attributes[self.logical(attr)] = attr

        for attr in self.cube.details:
            self.attributes[self.logical(attr)] = attr

        for dim in self.cube.dimensions:
            for attr in dim.all_attributes():
                if not attr.dimension:
                    raise Exception("No dimension in attr %s" % attr)
                self.attributes[self.logical(attr)] = attr

    def all_attributes(self, expand_locales=False):
        """Return a list of all attributes of a cube. If `expand_locales` is
        ``True``, then localized logical reference is returned for each
        attribute's locale."""
        return self.attributes.values()

    def attribute(self, name):
        """Returns an attribute with logical reference `name`. """
        # TODO: If attribute is not found, returns `None` (yes or no?)

        return self.attributes[name]

    def logical(self, attribute, locale=None):
        """Returns logical reference as string for `attribute` in `dimension`.
        If `dimension` is ``Null`` then fact table is assumed. The logical
        reference might have following forms:

        * ``dimension.attribute`` - dimension attribute
        * ``attribute`` - fact measure or detail

        If `simplify_dimension_references` is ``True`` then references for
        flat dimensios without details is `dimension`.

        If `locale` is specified, then locale is added to the reference. This
        is used by backends and other mappers, it has no real use in end-user
        browsing.
        """

        dimension = attribute.dimension

        if dimension:
            simplify = self.simplify_dimension_references and \
                               (dimension.is_flat and not dimension.has_details)
        else:
            simplify = False

        reference = attribute.ref(simplify, locale)

        return reference

    def split_logical(self, reference):
        """Returns tuple (`dimension`, `attribute`) from `logical_reference` string. Syntax
        of the string is: ``dimensions.attribute``."""

        split = reference.split(".")

        if len(split) > 1:
            dim_name = split[0]
            attr_name = ".".join(split[1:])
            return (dim_name, attr_name)
        else:
            return (None, reference)

    def physical(self, attribute, locale=None):
        """Returns physical reference as tuple for `attribute`, which should
        be an instance of :class:`cubes.model.Attribute`. If there is no
        dimension specified in attribute, then fact table is assumed. The
        returned tuple has structure: (`schema`, `table`, `column`).

        This method should be implemented by `Mapper` subclasses.
        """

        raise NotImplementedError

    def map_attributes(self, attributes, expand_locales=False):
        """Convert `attributes` to physical attributes. If `expand_locales` is
        ``True`` then physical reference for every attribute locale is
        returned."""

        if expand_locales:
            physical_attrs = []

            for attr in attributes:
                if attr.locales:
                    refs = [self.physical(attr, locale) for locale in attr.locales]
                else:
                    refs = [self.physical(attr)]
                physical_attrs += refs
        else:
            physical_attrs = [self.physical(attr) for attr in attributes]

        return physical_attrs

    def relevant_joins(self, attributes):
        """Get relevant joins to the attributes - list of joins that
        are required to be able to acces specified attributes. `attributes`
        is a list of three element tuples: (`schema`, `table`, `attribute`).

        Subclasses sohuld implement this method.
        """

        raise NotImplementedError

class SnowflakeMapper(Mapper):
    """Mapper is core clas for translating logical model to physical
    database schema.
    """
    # WARNING: do not put any SQL/engine/connection related stuff into this
    # class yet. It might be moved to the cubes as one of top-level modules
    # and subclassed here.

    def __init__(self, cube, mappings=None, locale=None, schema=None,
                    fact_name=None, dimension_prefix=None, joins=None,
                    dimension_schema=None, **options):

        """A snowflake schema mapper for a cube. The mapper creates required
        joins, resolves table names and maps logical references to tables and
        respective columns.

        Attributes:

        * `cube` - mapped cube
        * `mappings` – dictionary containing mappings
        * `simplify_dimension_references` – references for flat dimensions
          (with one level and no details) will be just dimension names, no
          attribute name. Might be useful when using single-table schema, for
          example, with couple of one-column dimensions.
        * `dimension_prefix` – default prefix of dimension tables, if
          default table name is used in physical reference construction
        * `fact_name` – fact name, if not specified then `cube.name` is used
        * `schema` – default database schema
        * `dimension_prefix` – prefix for dimension tables
        * `dimension_schema` – schema whre dimension tables are stored (if
          different than fact table schema)
        `mappings` is a dictionary where keys are logical attribute references
        and values are table column references. The keys are mostly in the
        form:

        * ``attribute`` for measures and fact details
        * ``attribute.locale`` for localized fact details
        * ``dimension.attribute`` for dimension attributes
        * ``dimension.attribute.locale`` for localized dimension attributes

        The values might be specified as strings in the form ``table.column``
        (covering most of the cases) or as a dictionary with keys ``schema``,
        ``table`` and ``column`` for more customized references.

        .. In the future it might support automatic join detection.

        """

        super(SnowflakeMapper, self).__init__(cube, locale=locale,
                                        schema=schema, fact_name=fact_name,
                                        **options)

        self.mappings = mappings or cube.mappings
        self.dimension_prefix = dimension_prefix
        self.dimension_schema = dimension_schema

        self._collect_joins(joins or cube.joins)

    def _collect_joins(self, joins):
        """Collects joins and coalesce physical references. `joins` is a
        dictionary with keys: `master`, `detail` reffering to master and
        detail keys. `alias` is used to give alternative name to a table when
        two tables are being joined."""

        joins = joins or []

        self.joins = []

        for join in joins:
            master = coalesce_physical(join["master"],self.fact_name,schema=self.schema)
            detail = coalesce_physical(join["detail"],schema=self.schema)
            self.logger.debug("collecting join %s - %s" % (tuple(master), tuple(detail)))
            self.joins.append(TableJoin(master, detail, join.get("alias")))

    def physical(self, attribute, locale=None):
        """Returns physical reference as tuple for `attribute`, which should
        be an instance of :class:`cubes.model.Attribute`. If there is no
        dimension specified in attribute, then fact table is assumed. The
        returned tuple has structure: (`schema`, `table`, `column`).

        The algorithm to find physicl reference is as follows::

            IF localization is requested:
                IF is attribute is localizable:
                    IF requested locale is one of attribute locales
                        USE requested locale
                    ELSE
                        USE default attribute locale
                ELSE
                    do not localize

            IF mappings exist:
                GET string for logical reference
                IF locale:
                    append '.' and locale to the logical reference

                IF mapping value exists for localized logical reference
                    USE value as reference

            IF no mappings OR no mapping was found:
                column name is attribute name

                IF locale:
                    append '_' and locale to the column name

                IF dimension specified:
                    # Example: 'date.year' -> 'date.year'
                    table name is dimension name

                    IF there is dimension table prefix
                        use the prefix for table name

                ELSE (if no dimension is specified):
                    # Example: 'date' -> 'fact.date'
                    table name is fact table name
        """

        reference = None
        dimension = attribute.dimension

        # Fix locale: if attribute is not localized, use none, if it is
        # localized, then use specified if exists otherwise use default
        # locale of the attribute (first one specified in the list)

        locale = locale or self.locale

        if attribute.locales:
            locale = locale if locale in attribute.locales \
                                else attribute.locales[0]
        else:
            locale = None

        # Try to get mapping if exists
        if self.cube.mappings:
            logical = self.logical(attribute, locale)

            # TODO: should default to non-localized reference if no mapping 
            # was found?
            mapped_ref = self.cube.mappings.get(logical)

            if mapped_ref:
                reference = coalesce_physical(mapped_ref, self.fact_name, self.schema)

        # No mappings exist or no mapping was found - we are going to create
        # default physical reference
        if not reference:
            column_name = attribute.name

            if locale:
                column_name += "_" + locale

            if dimension and not (self.simplify_dimension_references \
                                   and (dimension.is_flat
                                        and not dimension.has_details)):
                table_name = str(dimension)
                if self.dimension_prefix:
                    table_name = self.dimension_prefix + table_name

            else:
                table_name = self.fact_name

            schema = self.dimension_schema or self.schema
            reference = TableColumnReference(schema, table_name, column_name, None)

        return reference

    def table_map(self):
        """Return list of references to all tables. Keys are aliased
        tables: (`schema`, `aliased_table_name`) and values are
        real tables: (`schema`, `table_name`). Included is the fact table
        and all tables mentioned in joins.

        To get list of all physical tables where aliased tablesare included
        only once::

            finder = JoinFinder(cube, joins, fact_name)
            tables = set(finder.table_map().keys())
        """

        tables = {
            (self.schema, self.fact_name): (self.schema, self.fact_name)
        }

        for join in self.joins:
            if not join.detail.table or join.detail.table == self.fact_name:
                raise BackendError("Detail table name should be present and should not be a fact table.")

            ref = (join.master.schema, join.master.table)
            tables[ref] = ref

            ref = (join.detail.schema, join.alias or join.detail.table)
            tables[ref] = (join.detail.schema, join.detail.table)

        return tables

    def relevant_joins(self, attributes):
        """Get relevant joins to the attributes - list of joins that
        are required to be able to acces specified attributes. `attributes`
        is a list of three element tuples: (`schema`, `table`, `attribute`).
        """

        # Attribute: (schema, table, column)
        # Join: ((schema, table, column), (schema, table, column), alias)

        self.logger.debug("getting relevant joins for %s attributes" % len(attributes))

        if not self.joins:
            self.logger.debug("no joins to be searched for")

        tables_to_join = set((ref[0], ref[1]) for ref in attributes)
        joined_tables = set()
        joined_tables.add( (self.schema, self.fact_name) )

        joins = []
        self.logger.debug("tables to join: %s" % tables_to_join)

        while tables_to_join:
            table = tables_to_join.pop()
            # self.logger.debug("joining table %s" % (table, ))

            for order, join in enumerate(self.joins):
                # self.logger.debug("testing join: %s" % (join, ))
                # print "--- testing join: %s" % (join, )
                master = (join.master.schema, join.master.table)
                detail = (join.detail.schema, join.alias or join.detail.table)

                if table == detail:
                    # self.logger.debug("detail matches")
                    # Preserve join order
                    joins.append( (order, join) )

                    if master not in joined_tables:
                        self.logger.debug("adding master %s to be joined" % (master, ))
                        tables_to_join.add(master)

                    self.logger.debug("joined detail %s" % (detail, ) )
                    joined_tables.add(detail)
                    break

        # FIXME: is join order important? if yes, we should sort them here
        self.logger.debug("%s tables joined (of %s joins)" % (len(joins), len(self.joins)) )

        # Sort joins according to original order specified in the model
        joins.sort()
        self.logger.debug("joined tables: %s" % ([join[1].detail.table for join in
                                                                joins], ) )

        # Retrieve actual joins from tuples. Remember? We preserved order.
        joins = [join[1] for join in joins]
        return joins


class DenormalizedMapper(Mapper):
    def __init__(self, cube, locale=None, schema=None,
                    fact_name=None, denormalized_view_prefix=None,
                    denormalized_view_schema=None,
                    **options):

        """Creates a mapper for a cube that has data stored in a denormalized
        view/table.

        Attributes:

        * `denormalized_view_prefix` – default prefix used for constructing
           view name from cube name
        * `fact_name` – fact name, if not specified then `cube.name` is used
        * `schema` – schema where the denormalized view is stored
        * `fact_schema` – database schema for the original fact table
        """

        super(DenormalizedMapper, self).__init__(cube, locale=locale,
                                        schema=schema, fact_name=fact_name)

        dview_prefix = denormalized_view_prefix or ""

        # FIXME: this hides original fact name, we do not want that

        self.fact_name = options.get("denormalized_view") or dview_prefix + self.cube.name
        self.fact_schema = self.schema
        self.schema = self.schema or denormalized_view_schema

    def physical(self, attribute, locale=None):
        """Returns same name as localized logical reference.
        """

        locale = locale or self.locale
        try:
            if attribute.locales:
                locale = locale if locale in attribute.locales \
                                    else attribute.locales[0]
            else:
                locale = None
        except:
            locale = None

        column_name = self.logical(attribute, locale)
        reference = TableColumnReference(self.schema,
                                          self.fact_name,
                                          column_name,
                                          None)

        return reference

    def relevant_joins(self, attributes):
        """Returns an empty list. No joins are necessary for denormalized
        view.
        """

        self.logger.debug("getting relevant joins: not needed for denormalized table")

        return []

class StarMapper(Mapper):
    def __init__(self, cube, locale=None, schema=None, fact_name=None,
                 dimension_prefix=None, joins=None, dimension_schema=None,
                 **options):

        """A snowflake schema mapper for a cube. The mapper creates required
        joins, resolves table names and maps logical references to tables and
        respective columns.

        Attributes:

        * `cube` - mapped cube
        * `simplify_dimension_references` – references for flat dimensions
          (with one level and no details) will be just dimension names, no
          attribute name. Might be useful when using single-table schema, for
          example, with couple of one-column dimensions.
        * `dimension_prefix` – default prefix of dimension tables, if
          default table name is used in physical reference construction
        * `fact_name` – fact name, if not specified then `cube.name` is used
        * `schema` – default database schema
        * `dimension_schema` – schema whre dimension tables are stored (if
          different than fact table schema)

        """

        super(SnowflakeMapper, self).__init__(cube, locale=locale,
                                        schema=schema, fact_name=fact_name,
                                        **options)

        self.dimension_prefix = dimension_prefix
        self.dimension_schema = dimension_schema

    def physical(self, attribute, locale=None, iskey=False):
        """Returns same name as localized logical reference.
        """

        reference = None
        dimension = attribute.dimension

        # Fix locale: if attribute is not localized, use none, if it is
        # localized, then use specified if exists otherwise use default
        # locale of the attribute (first one specified in the list)

        locale = locale or self.locale

        if attribute.locales:
            locale = locale if locale in attribute.locales \
                                else attribute.locales[0]
        else:
            locale = None

        column_name = attribute.name

        if locale:
            column_name += "_" + locale

        if dimension and not iskey \
                and not (self.simplify_dimension_references \
                            and (dimension.is_flat
                            and not dimension.has_details)):
            table_name = str(dimension)
            if self.dimension_prefix:
                table_name = self.dimension_prefix + table_name

        else:
            table_name = self.fact_name

        if dimension and not iskey:
            schema = self.dimension_schema or self.schema
        else:
            schema = self.schema

        reference = TableColumnReference(schema, table_name, column_name, None)

        return reference

    def relevant_joins(self, attributes):
        """Returns a list of joins for requested attributes."""

        for attribute in attributes:
            if attribute.dimension:
                schema = self.dimension_schema or self.schema
                table = self
            else:
                schema = self.schema





        return []
