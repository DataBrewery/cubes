from .errors import *
from .browser import AggregationBrowser
from .extensions import get_namespace, initialize_namespace

__all__ = (
            "open_store",
            "Store"
        )


def open_store(name, **options):
    """Gets a new instance of a model provider with name `name`."""

    ns = get_namespace("stores")
    if not ns:
        ns = initialize_namespace("stores", root_class=Store,
                                  suffix="_store")

    try:
        factory = ns[name]
    except KeyError:
        raise ConfigurationError("Unknown store '%s'" % name)

    return factory(**options)


def create_browser(type_, cube, store, locale, **options):
    """Creates a new browser."""

    ns = get_namespace("browsers")
    if not ns:
        ns = initialize_namespace("browsers", root_class=AggregationBrowser,
                                  suffix="_browser")

    try:
        factory = ns[type_]
    except KeyError:
        raise ConfigurationError("Unable to find browser of type '%s'" % type_)

    return factory(cube=cube, store=store, locale=locale, **options)


class Store(object):
    """Abstract class to find other stores through the class hierarchy."""
    def model_provider_name(self):
        raise NotImplementedError("Subclasses must implement")
