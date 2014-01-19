from .errors import *
from .extensions import Extensible

__all__ = (
            "Store"
        )


class Store(Extensible):
    """Abstract class to find other stores through the class hierarchy."""
    pass
