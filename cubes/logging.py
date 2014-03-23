# -*- coding: utf-8 -*-

from __future__ import absolute_import

from logging import getLogger, Formatter, StreamHandler, FileHandler
from .errors import *

__all__ = [
           "logger_name",
           "get_logger",
           "create_logger",
           ]

logger_name = "cubes"
logger = None

def get_logger(toFile = False):
    """Get brewery default logger"""
    global logger
    
    if logger:
        return logger
    else:
        return create_logger(toFile)

def create_logger(toFile):
    """Create a default logger"""
    global logger
    logger = getLogger(logger_name)
    formatter = Formatter(fmt='%(asctime)s %(levelname)s %(message)s')
    
    if not toFile:
        #create a default logger
        handler = StreamHandler()
    else:
        #create a logger which logs to a file
        handler = FileHandler(toFile)
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

