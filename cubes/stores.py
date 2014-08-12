# -*- coding: utf-8 -*-

from .errors import *
from .extensions import Extensible

__all__ = (
            "Store"
        )


class Store(Extensible):
    """Abstract class to find other stores through the class hierarchy."""

    """Name of a model provider type associated with this store."""
    related_model_provider = None

    def __init__(self, store_name, store_type, **options):
        self.store_name = store_name
        self.store_type = store_type
        self.options = options
