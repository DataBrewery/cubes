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
