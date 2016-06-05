# -*- encoding: utf-8 -*-
"""Logical to Physical Mappers"""

from __future__ import absolute_import

import re

from ..errors import ModelError
from ..datastructures import AttributeDict

from .query import to_column


# Note about the future of this module:
#
# Mapper should map the whole schema – mutliple facts and multiple dimensions.
# It should be decoupled from the cube and probably associated with the store
# (or store associated with the mapping)
#

__all__ = (
    "distill_naming",
    "Naming",
    "DEFAULT_KEY_FIELD",

    "Mapper",
    "StarSchemaMapper",
    "DenormalizedMapper",
    "map_base_attributes",
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

    "denormalized_prefix": None,
    "denormalized_suffix": None,

    "aggregated_prefix": None,
    "aggregated_suffix": None,

    "fact_key": DEFAULT_FACT_KEY,
    "dimension_key": DEFAULT_DIMENSION_KEY,
    "explicit_dimension_primary": False,

    "schema": None,
    "fact_schema": None,
    "dimension_schema": None,
    "aggregate_schema": None,
}


def distill_naming(dictionary):
    """Distill only keys and values related to the naming conventions."""
    d = {key: value for key, value in dictionary.items()
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

        pat = re.compile("^{}(?P<name>.*){}$"
                         .format(self.dimension_prefix or "", self.dimension_suffix or ""))
        self["dim_name_pattern"] = pat

        pat = re.compile("^{}(?P<name>.*){}$"
                         .format(self.fact_prefix or "", self.fact_suffix or ""))
        self["fact_name_pattern"] = pat

        pat = re.compile("^{}(?P<name>.*){}$"
                         .format(self.dimension_key_prefix or "", self.dimension_key_suffix or ""))
        self["dim_key_pattern"] = pat

    def dimension_table_name(self, name):
        """Constructs a physical dimension table name for dimension `name`"""

        table_name = "{}{}{}".format(self.dimension_prefix or "",
                                     name,
                                     self.dimension_suffix or "")
        return table_name

    def fact_table_name(self, name):
        """Constructs a physical fact table name for fact/cube `name`"""

        table_name = "{}{}{}".format(self.fact_prefix or "",
                                     name,
                                     self.fact_suffix or "")
        return table_name

    def denormalized_table_name(self, name):
        """Constructs a physical fact table name for fact/cube `name`"""

        table_name = "{}{}{}".format(self.denormalized_prefix or "",
                                     name,
                                     self.denormalized_suffix or "")
        return table_name

    # TODO: require list of dimensions here
    def aggregated_table_name(self, name):
        """Constructs a physical fact table name for fact/cube `name`"""

        table_name = "{}{}{}".format(self.aggregated_prefix or "",
                                     name,
                                     self.aggregated_suffix or "")
        return table_name

    def dimension_primary_key(self, name):
        """Constructs a dimension primary key name for dimension `name`"""

        if self.explicit_dimension_primary:
            key = "{}{}{}".format(self.dimension_key_prefix or "",
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


class Mapper(object):
    """A dictionary-like object that provides physical column references for
    cube attributes. Does implicit mapping of an attribute.

    .. versionchanged:: 1.1
    """

    def __init__(self, cube, naming, locale=None):
        """Creates a mapping for `cube` using `naming` conventions within
        optional `locale`. `naming` has to be a :class:`cubes.Naming`
        object."""
        self.naming = naming
        self.locale = locale
        self.mappings = cube.mappings or {}
        self.fact_name = cube.fact or naming.fact_table_name(cube.name)


    def __getitem__(self, attribute):
        """Returns implicit physical column reference for `attribute`, which
        should be an instance of :class:`cubes.model.Attribute`. If there is
        no dimension specified in attribute, then fact table is assumed. The
        returned reference has attributes `schema`, `table`, `column`,
        `extract`.  """

        column_name = attribute.name

        if attribute.is_localizable():
            locale = self.locale if self.locale in attribute.locales \
                                else attribute.locales[0]

            column_name = "{}_{}".format(column_name, locale)

        schema, table = self.attribute_table(attribute)

        return to_column((schema, table, column_name))

    def attribute_table(self, attribute):
        """Return a tuple (schema, table) for attribute."""

        dimension = attribute.dimension

        if dimension:
            schema = self.naming.dimension_schema or self.naming.schema
            if dimension.is_flat and not dimension.has_details:
                table = self.fact_name
            else:
                table = self.naming.dimension_table_name(dimension)

        else:
            table = self.fact_name
            schema = self.naming.schema

        return (schema, table)


class DenormalizedMapper(Mapper):
    def __getitem__(self, attribute):
        if attribute.expression:
            raise ModelError("Attribute '{}' has an expression, it can not "
                             "have a direct physical representation"
                             .format(attribute.name))

        return super(DenormalizedMapper, self).__getitem__(attribute)


class StarSchemaMapper(Mapper):
    def __getitem__(self, attribute):
        """Find physical reference for a star schema as follows:

        1. if there is mapping for `dimension.attribute`, use the mapping
        2. if there is no mapping or no mapping was found, then use table
        `dimension` or fact table, if attribute does not belong to a
        dimension and column `attribute`

        If table prefixes and suffixes are used, then they are
        prepended/appended to the table tame in the implicit mapping.

        If localization is requested and the attribute is localizable, then
        suffix in the form `_LOCALE` where `LOCALE` is the locale name will be
        added to search for mapping or for implicit attribute creation such as
        `name_sk` for attribute `name` and locale `sk`.
        """

        if attribute.expression:
            raise ModelError("Attribute '{}' has an expression, it can not "
                             "have a direct physical representation"
                             .format(attribute.name))

        # Fix locale: if attribute is not localized, use none, if it is
        # localized, then use specified if exists otherwise use default
        # locale of the attribute (first one specified in the list)

        if attribute.is_localizable():
            locale = self.locale if self.locale in attribute.locales \
                                else attribute.locales[0]
        else:
            locale = None

        logical = attribute.localized_ref(locale)

        physical = self.mappings.get(logical)

        if physical:
            # TODO: Should we not get defaults here somehow?
            column = to_column(physical)
            return column

        # No mappings exist or no mapping was found - we are going to create
        # default physical reference
        return super(StarSchemaMapper, self).__getitem__(attribute)


def map_base_attributes(cube, mapper_class, naming, locale=None):
    """Map all base attributes of `cube` using mapping function `mapper`.
    `naming` is a naming convention object. Returns a tuple (`fact_name`,
    `mapping`) where `fact_name` is a fact table name and `mapping` is a
    dictionary of attribute references and their physical column
    references."""

    base = [attr for attr in cube.all_attributes if attr.is_base]

    mapper = mapper_class(cube, naming, locale)
    mapped = {attr.ref:mapper[attr] for attr in base}

    return (mapper.fact_name, mapped)

