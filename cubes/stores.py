# -*- coding: utf-8 -*-

from typing import Any, Optional

from .ext import Extensible
from .types import JSONType

__all__ = "Store"

# Note: this class does not have much use right now besides being discoverable
# by custom plugin system in cubes.
# TODO: remove requirement for store_name and store_type
class Store(Extensible, abstract=True):
    """Abstract class to find other stores through the class hierarchy."""

    """Name of a model provider type associated with this store."""
    __extension_type__ = "store"

    related_model_provider: Optional[str] = None
    default_browser_name: Optional[str] = None
    store_type: str

    options: JSONType

    def __init__(self, **options: Any) -> None:
        # We store the parsed options from the store configuration here
        self.options = options

        # TODO: this is just backward compatibility, remove this (make this
        # class variable)
        self.store_type = options.get("store_type")
