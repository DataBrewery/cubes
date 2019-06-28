# -*- coding: utf-8 -*-

from typing import Optional, Union
from logging import getLogger, Formatter, StreamHandler, FileHandler, Logger

__all__ = ["get_logger", "create_logger"]

DEFAULT_LOGGER_NAME = "cubes"
DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(message)s"
logger: Optional[Logger] = None

# TODO: make name first
def get_logger(path: str = None, format_: str = None, name: str = None) -> Logger:
    """Get brewery default logger"""
    global logger

    if logger:
        return logger
    else:
        return create_logger(path, format_, name)


def create_logger(path: str = None, format_: str = None, name: str = None) -> Logger:
    """Create a default logger"""
    global logger
    logger = getLogger(name or DEFAULT_LOGGER_NAME)
    logger.propagate = False

    if not logger.handlers:
        formatter = Formatter(fmt=format_ or DEFAULT_FORMAT)

        handler: Union[StreamHandler, FileHandler]

        if path:
            # create a logger which logs to a file
            handler = FileHandler(path)
        else:
            # create a default logger
            handler = StreamHandler()

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
