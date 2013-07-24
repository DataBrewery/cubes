# -*- coding: utf-8 -*-
"""Logical to Physical Mappers"""

import collections
from cubes.common import get_logger
from cubes.errors import *

__all__ = (
    "Mapper",
)

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

    def set_locale(self, locale):
        """Change the mapper's locale"""
        self.locale = locale
        self._collect_attributes()

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
