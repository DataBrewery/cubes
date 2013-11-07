# -*- coding=utf -*-

from __future__ import absolute_import

from logging import getLogger, Formatter, StreamHandler
from .errors import *

__all__ = [
    "logger_name",
    "get_logger",
    "create_logger",
]

logger_name = "cubes"
logger = None

def get_logger():
    """Get brewery default logger"""
    global logger

    if logger:
        return logger
    else:
        return create_logger()

def create_logger(level=None):
    """Create a default logger"""
    global logger
    logger = getLogger(logger_name)

    formatter = Formatter(fmt='%(asctime)s %(levelname)s %(message)s')

    handler = StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if level:
        logger.setLevel(level.upper())

    return logger

