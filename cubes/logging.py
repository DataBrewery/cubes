# -*- coding: utf-8 -*-

from __future__ import absolute_import

from logging import getLogger, Formatter, StreamHandler, FileHandler

__all__ = [
    "get_logger",
    "create_logger",
]

DEFAULT_LOGGER_NAME = "cubes"
DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(message)s"
logger = None

# TODO: make name first
def get_logger(path=None, format_=None, name=None):
    """Get brewery default logger"""
    global logger

    if logger:
        return logger
    else:
        return create_logger(path, format_, name)

def create_logger(path=None, format_=None, name=None):
    """Create a default logger"""
    global logger
    logger = getLogger(name or DEFAULT_LOGGER_NAME)
    logger.propagate = False

    if not logger.handlers:
        formatter = Formatter(fmt=format_ or DEFAULT_FORMAT)

        if path:
            # create a logger which logs to a file
            handler = FileHandler(path)
        else:
            # create a default logger
            handler = StreamHandler()

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

