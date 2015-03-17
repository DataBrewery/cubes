# -*- encoding: utf-8 -*-
"""Logical to Physical Mappers"""

from __future__ import absolute_import

from collections import namedtuple

from ..logging import get_logger
from ..errors import BackendError, ModelError
from ..mapper import Mapper
from ..model import AttributeBase
from ..datastructures import AttributeDict
from .. import compat
import re

from .schema import to_column


# Note about the future of this module:
#
# Mapper should map the whole schema – mutliple facts and multiple dimensions.
# It should be decoupled from the cube and probably associated with the store
# (or store associated with the mapping)
#

__all__ = (
    "SnowflakeMapper",
    "DenormalizedMapper",
    "distill_naming",
    "Naming",
    "DEFAULT_KEY_FIELD"
)


DEFAULT_KEY_FIELD = "id"

DEFAULT_FACT_KEY = 'id'
DEFAULT_DIMENSION_KEY = 'id'

# Note: Only keys in this dictionary are allowed in the `naming` dictionary.
# All other keys are ignored.

NAMING_DEFAULTS = {
    "fact_prefix": None,
    "fact_suffix": None,
    "dimension_prefix": None,
    "dimension_suffix": None,
    "dimension_key_prefix": None,
    "dimension_key_suffix": None,
    "fact_key": DEFAULT_FACT_KEY,
    "dimension_key": DEFAULT_DIMENSION_KEY,
    "explicit_dimension_primary": False,

    "schema": None,
    "fact_schema": None,
    "dimension_schema": None,
}


def distill_naming(dictionary):
    """Distill only keys and values related to the naming conventions."""
    d = {key: value for key, value
                    in dictionary.items()
                    if key in NAMING_DEFAULTS}

    return Naming(d)


def _match_names(pattern, names):
    """Match names to patterns and return a tuple of matching name with
    extracted value (stripped of suffix/prefix)."""

    result = []

    for name in names:
        match = pattern.match(name)
        if match:
            result.append((name, match.group("name")))

    return result


class Naming(AttributeDict):
    """Naming conventions for SQL tables. Naming properties can be accessed as
    a dictionary keys or as direct attributes. The naming properties are:

    * `fact_prefix` – prefix for fact tables
    * `fact_suffix` – suffix for fact tables
    * `dimension_prefix` – prefix for dimension tables
    * `dimension_suffix` – suffix for dimension tables
    * `dimension_key_prefix` – prefix for dimension foreign keys
    * `dimension_key_suffix` – suffix for dimension foreign keys
    * `fact_key` – name of fact table primary key (defaults to ``id`` if not
      specified)
    * `dimension_key` – name of dimension table primary key (defaults to
      ``id`` if not specified)
    * `explicit_dimension_primary` – whether the primary key of dimension
      table contains dimension name explicitly.

    If the `explicit_dimension_primary` is `True`, then all dimension tables
    are expected to have the primary key in the same format as foreign
    dimension keys. For example if the foreign dimension keys are
    ``customer_key`` then primary key of customer dimension table is also
    ``customer_key`` as oposed to just ``key``. The `dimension_key` naming
    property is ignored.


    Additional information that can be used by the mapper:

    * `schema` – default schema
    * `fact_schema` – schema where all fact tables are stored
    * `dimension_schema` – schema where dimension tables are stored

    Recommended values: `fact_prefix` = ``ft_``, `dimension_prefix` =
    ``dm_``, `explicit_dimension_primary` = ``True``.
    """

    def __init__(self, *args, **kwargs):
        """Creates a `Naming` object instance from a dictionary. If `fact_key`
        or `dimension_key` are not specified, then they are set to ``id`` by
        default."""

        super(Naming, self).__init__(*args, **kwargs)

        # Set the defaults
        for key, value in NAMING_DEFAULTS.items():
            if key not in self:
                self[key] = value

        pat = re.compile("^{}(?P<name>.*){}$".format(self.dimension_prefix or "",
                                                 self.dimension_suffix or ""))
        self["dim_name_pattern"] = pat

        pat = re.compile("^{}(?P<name>.*){}$".format(self.fact_prefix or "",
                                                 self.fact_suffix or ""))
        self["fact_name_pattern"] = pat

        pat = re.compile("^{}(?P<name>.*){}$".format(self.dimension_key_prefix or "",
                                                 self.dimension_key_suffix or ""))
        self["dim_key_pattern"] = pat

    def dimension_table_name(self, name):
        """Constructs a physical dimension table name for dimension `name`"""

        table_name = "{}{}{}".format(
                            self.dimension_prefix or "",
                            name,
                            self.dimension_suffix or "")
        return table_name

    def fact_table_name(self, name):
        """Constructs a physical fact table name for fact/cube `name`"""

        table_name = "{}{}{}".format(
                            self.fact_prefix or "",
                            name,
                            self.fact_suffix or "")
        return table_name

    def dimension_primary_key(self, name):
        """Constructs a dimension primary key name for dimension `name`"""

        if self.explicit_dimension_primary:
            key = "{}{}{}".format(
                    self.dimension_key_prefix or "",
                    name,
                    self.dimension_key_suffix or "")
            return key
        else:
            return self.dimension_key

    def dimension_keys(self, keys):
        """Return a list of tuples (`key`, `dimension`) for every key in
        `keys` that matches dimension key naming. Useful when trying to
        identify dimensions and their foreign keys in a fact table that
        follows the naming convetion."""

        return _match_names(self.dim_key_pattern, keys)

    def dimensions(self, table_names):
        """Return a list of tuples (`table`, `dimension`) for all tables that
        match dimension naming scheme. Usefult when trying to identify
        dimension tables in a database that follow the naming convention."""

        return _match_names(self.dim_name_pattern, table_names)

    def facts(self, table_names):
        """Return a list of tuples (`table`, `fact`) for all tables that
        match fact table naming scheme. Useful when trying to identify fact
        tables in a database that follow the naming convention."""

        return _match_names(self.fact_name_pattern, table_names)


class SnowflakeMapper(Mapper):
    """Mapper is core clas for translating logical model to physical
    database schema.
    """
    # WARNING: do not put any SQL/engine/connection related stuff into this
    # class yet. It might be moved to the cubes as one of top-level modules
    # and subclassed here.

    def __init__(self, cube, mappings=None, locale=None, fact_name=None,
                 **naming):

        """A snowflake schema mapper for a cube. The mapper creates required
        joins, resolves table names and maps logical references to tables and
        respective columns.

        Attributes:

        * `cube` - mapped cube
        * `mappings` – dictionary containing mappings
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

        super(SnowflakeMapper, self).__init__(cube, locale=locale, **naming)


        self.mappings = mappings or cube.mappings

        self.naming = distill_naming(naming)

        if not (fact_name or self.cube.fact or self.cube.basename):
            raise ModelError("Can not determine cube fact name")

        self.fact_name = fact_name \
                            or self.cube.fact \
                            or self.naming.fact_table_name(self.cube.basename)

        self.schema = self.naming.schema

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

        schema = self.naming.dimension_schema or self.schema

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
            if dimension \
                    and not (dimension.is_flat and not dimension.has_details):
                table_name = self.naming.dimension_table_name(dimension)
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


# TODO: obsolete, to be reviewed
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


