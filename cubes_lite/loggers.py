# -*- coding: utf-8 -*-

from __future__ import absolute_import

from loggers import getLogger, Formatter, StreamHandler

__all__ = (
    'get_logger',
)


DEFAULT_LOGGER_NAME = 'cubes_lite'
DEFAULT_FORMAT = '%(asctime)s %(levelname)s %(message)s'

# used as global
logger = None


def get_logger(name=DEFAULT_LOGGER_NAME, format_=None):
    """Get brewery default logger"""
    global logger

    if not logger:
        logger = create_logger(name)

    return logger


def create_logger(name, format_=DEFAULT_FORMAT):
    logger = getLogger(name)
    logger.propagate = False

    if not logger.handlers:
        formatter = Formatter(fmt=format_ or DEFAULT_FORMAT)

        handler = StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
