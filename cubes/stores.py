# -*- coding: utf-8 -*-

__all__ = (
    "Store"
)


# Note: this class does not have much use right now besides being discoverable
# by custom plugin system in cubes.
# TODO: remove requirement for store_name and store_type
class Store(object):
    """Abstract class to find other stores through the class hierarchy."""

    """Name of a model provider type associated with this store."""
    related_model_provider = None
    store_type = None

    def __init__(self, **options):
        # We store the parsed options from the store configuration here
        self.options = options

        # TODO: this is just backward compatibility, remove this (make this
        # class variable)
        self.store_type = options.get("store_type")
