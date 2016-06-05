# -*- coding: utf-8 -*-
"""Logical to Physical Mappers"""

import collections

from .logging import get_logger

__all__ = (
    "Mapper",
)

class Mapper(object):
    """Mapper is core class for translating logical model to physical database
    schema.
    """
    # WARNING: do not put any SQL/engine/connection related stuff into this
    # class yet. It might be moved to the cubes as one of top-level modules
    # and subclassed here.

    def __init__(self, cube, locale=None, **naming):
        """Abstract class for mappers which maps logical references to
        physical references (tables and columns).

        Attributes:

        * `cube` - mapped cube
        * `fact_name` – fact name, if not specified then `cube.name` is used
        * `schema` – default database schema

        """

        super(Mapper, self).__init__()

        if cube is None:
            raise Exception("Cube for mapper should not be None.")

        self.logger = get_logger()

        self.cube = cube

        self.mappings = self.cube.mappings
        self.locale = locale

        # TODO: remove this (should be in SQL only)

        self._collect_attributes()

    def _collect_attributes(self):
        """Collect all cube attributes and create a dictionary where keys are
        logical references and values are `cubes.model.Attribute` objects.
        This method should be used after each cube or mappings change.
        """

        self.attributes = collections.OrderedDict()

        for attr in self.cube.all_fact_attributes:
            self.attributes[self.logical(attr)] = attr

    def set_locale(self, locale):
        """Change the mapper's locale"""
        self.locale = locale
        self._collect_attributes()

    # TODO: depreciate in favor of Cube.all_attributes
    def all_attributes(self, expand_locales=False):
        """Return a list of all attributes of a cube. If `expand_locales` is
        ``True``, then localized logical reference is returned for each
        attribute's locale."""
        return self.attributes.values()

    # TODO: depreciate in favor of Cube.attribute
    def attribute(self, name):
        """Returns an attribute with logical reference `name`. """
        # TODO: If attribute is not found, returns `None` (yes or no?)

        return self.attributes[name]

    # TODO: is this necessary after removing of 'simplify'? Reconsider
    # requirement for existence of this one.
    def logical(self, attribute, locale=None):
        """Returns logical reference as string for `attribute` in `dimension`.
        If `dimension` is ``Null`` then fact table is assumed. The logical
        reference might have following forms:

        * ``dimension.attribute`` - dimension attribute
        * ``attribute`` - fact measure or detail

        If `locale` is specified, then locale is added to the reference. This
        is used by backends and other mappers, it has no real use in end-user
        browsing.
        """

        reference = attribute.localized_ref(locale)

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
        """Returns physical reference for attribute. Returned value is backend
        specific. Default implementation returns a value from the mapping
        dictionary.

        This method should be implemented by `Mapper` subclasses.
        """

        return self.mappings.get(self.logical(attribute, locale))

