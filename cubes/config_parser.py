# -*- encoding: utf-8 -*-

"""Contains the parser of the slicer configuration."""

from . import compat
from .errors import ConfigurationError


def read_slicer_config(config):
    """Read the slicer configuration.

    If config is a string, it should be the path to the config file.
    If config is None, it return a new Configuration() from the constructor.
    If config is already a Configuration, the fuction return it.

    Raise ConfigurationError in the other case.
    """
    if config is None:
        return compat.ConfigParser()
    elif isinstance(config, compat.string_type):
        try:
            path = config
            config = compat.ConfigParser()
            config.read(path)
        except Exception as e:
            raise ConfigurationError("Unable to load configuration: %s" % e)
    elif not isinstance(config, compat.ConfigParser):
        raise ConfigurationError("config should be a ConfigParser instance,"
                                 " but is %r" % (type(config),)
                                 )
    return config
