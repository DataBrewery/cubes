# -*- coding: utf-8 -*-
"""Logical to Physical Mappers."""

# TODO: This should be moved under query sub-module

import collections
from logging import Logger
from typing import Any, Collection, Dict, Optional, Tuple

from .logging import get_logger
from .metadata.attributes import AttributeBase
from .metadata.cube import Cube
from .types import JSONType

__all__ = ("Mapper",)


class Mapper:
    """Mapper is core class for translating logical model to physical database
    schema."""

    # WARNING: do not put any SQL/engine/connection related stuff into this
    # class yet. It might be moved to the cubes as one of top-level modules
    # and subclassed here.

    logger: Logger
    cube: Cube
    mappings: JSONType
    locale: Optional[str]
    attributes: Dict[str, AttributeBase]

    def __init__(self, cube: Cube, locale: str = None, **naming: Any) -> None:
        """Abstract class for mappers which maps logical references to physical
        references (tables and columns).

        Attributes:

        * `cube` - mapped cube
        * `fact_name` – fact name, if not specified then `cube.name` is used
        * `schema` – default database schema
        """

        self.logger = get_logger()

        self.cube = cube
        self.mappings = self.cube.mappings or {}
        self.locale = locale
        self.attributes = collections.OrderedDict()

        # TODO: remove this (should be in SQL only)

        self._collect_attributes()

    def _collect_attributes(self) -> None:
        """Collect all cube attributes and create a dictionary where keys are
        logical references and values are `cubes.model.Attribute` objects.

        This method should be used after each cube or mappings change.
        """

        self.attributes = collections.OrderedDict()

        for attr in self.cube.all_fact_attributes:
            self.attributes[attr.localized_ref(self.locale)] = attr

    # FIXME: This is mutating (see #416)
    def set_locale(self, locale: str) -> None:
        """Change the mapper's locale."""
        self.locale = locale
        self._collect_attributes()

    def logical(self, attribute: AttributeBase, locale: str = None) -> str:
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

    def split_logical(self, reference: str) -> Tuple[Optional[str], str]:
        """Returns tuple (`dimension`, `attribute`) from `logical_reference`
        string.

        Syntax of the string is: ``dimensions.attribute``.
        """

        split = reference.split(".")

        if len(split) > 1:
            dim_name = split[0]
            attr_name = ".".join(split[1:])
            return (dim_name, attr_name)
        else:
            return (None, reference)

    def physical(self, attribute: AttributeBase, locale: str = None) -> str:
        """Returns physical reference for attribute. Returned value is backend
        specific. Default implementation returns a value from the mapping
        dictionary.

        This method should be implemented by `Mapper` subclasses.
        """

        return self.mappings.get(attribute.localized_ref(locale))
