# -*- encoding: utf-8 -*-
"""Logical to Physical Mappers"""

from __future__ import absolute_import

from collections import namedtuple

from ..logging import get_logger
from ..errors import BackendError, ModelError
from ..mapper import Mapper
from ..model import AttributeBase
from .. import compat

from .schema import to_column


__all__ = (
    "SnowflakeMapper",
    "DenormalizedMapper",
    "DEFAULT_KEY_FIELD"
)


DEFAULT_KEY_FIELD = "id"


class SnowflakeMapper(Mapper):
    """Mapper is core clas for translating logical model to physical
    database schema.
    """
    # WARNING: do not put any SQL/engine/connection related stuff into this
    # class yet. It might be moved to the cubes as one of top-level modules
    # and subclassed here.

    def __init__(self, cube, mappings=None, locale=None, schema=None,
                 fact_name=None, dimension_prefix=None, dimension_suffix=None,
                 joins=None, dimension_schema=None, **options):

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
        * `dimension_suffix` – default suffix of dimension tables, if
          default table name is used in physical reference construction
        * `fact_name` – fact name, if not specified then `cube.name` is used
        * `schema` – default database schema
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

        super(SnowflakeMapper, self).__init__(cube, locale=locale, **options)

        self.mappings = mappings or cube.mappings
        self.dimension_prefix = dimension_prefix or ""
        self.dimension_suffix = dimension_suffix or ""
        self.dimension_schema = dimension_schema

        fact_prefix = options.get("fact_prefix") or ""
        fact_suffix = options.get("fact_suffix") or ""

        if not (fact_name or self.cube.fact or self.cube.basename):
            raise ModelError("Can not determine cube fact name")

        self.fact_name = fact_name or self.cube.fact or "%s%s%s" % \
                            (fact_prefix, self.cube.basename, fact_suffix)
        self.schema = schema

    def physical(self, attribute, locale=None):
        """Returns physical reference as tuple for `attribute`, which should
        be an instance of :class:`cubes.model.Attribute`. If there is no
        dimension specified in attribute, then fact table is assumed. The
        returned tuple has structure: (`schema`, `table`, `column`).

        The algorithm to find physical reference is as follows:

        1. if there is mapping for `dimension.attribute`, use the mapping
        2. if there is no mapping or no mapping was found, then use table
        `dimension` or fact table, if attribute does not belong to a
        dimension and column `attribute`

        If table prefixes and suffixes are used, then they are
        prepended/appended to the table tame in the implicit mapping.

        If localization is requested and the attribute is localizable, then
        suffix `_LOCALE` whre `LOCALE` is the locale name will be added to
        search for mapping or for implicit attribute creation.
        """

        if attribute.expression:
            raise ModelError("Attribute '{}' has an expression, it can not "
                             "have a physical representation"
                             .format(attribute.name))

        schema = self.dimension_schema or self.schema

        reference = None

        # Fix locale: if attribute is not localized, use none, if it is
        # localized, then use specified if exists otherwise use default
        # locale of the attribute (first one specified in the list)

        locale = locale or self.locale

        if attribute.is_localizable():
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
                reference = to_column(mapped_ref,
                                       default_table=self.fact_name,
                                       default_schema=self.schema)

        # No mappings exist or no mapping was found - we are going to create
        # default physical reference
        if not reference:
            column_name = attribute.name

            if locale:
                column_name += "_" + locale

            # TODO: temporarily preserved. it should be attribute.owner
            dimension = attribute.dimension
            if dimension and not (self.simplify_dimension_references \
                                   and (dimension.is_flat
                                        and not dimension.has_details)):
                table_name = "%s%s%s" % (self.dimension_prefix, dimension, self.dimension_suffix)
            else:
                table_name = self.fact_name

            reference = to_column((schema, table_name, column_name))

        return reference

    # TODO: is this still needed?
    def physical_references(self, attributes, expand_locales=False):
        """Convert `attributes` to physical attributes. If `expand_locales` is
        ``True`` then physical reference for every attribute locale is
        returned."""

        if expand_locales:
            physical_attrs = []

            for attr in attributes:
                if attr.is_localizable():
                    refs = [self.physical(attr, locale) for locale in attr.locales]
                else:
                    refs = [self.physical(attr)]
                physical_attrs += refs
        else:
            physical_attrs = [self.physical(attr) for attr in attributes]

        return physical_attrs


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

        self.fact_name = options.get("denormalized_view") or dview_prefix + \
                            self.cube.basename
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
        reference = to_column((self.schema, self.fact_name, column_name))

        return reference


