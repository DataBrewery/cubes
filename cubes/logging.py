# -*- coding=utf -*-

from __future__ import absolute_import

from logging import getLogger, Formatter, StreamHandler
from contextlib import contextmanager
from collections import namedtuple
import time
import csv
import io

from .extensions import get_namespace, initialize_namespace
from .errors import *

__all__ = [
    "logger_name",
    "get_logger",
    "create_logger",
    "create_query_logger",
    "QueryLogger",
    "DefaultQueryLogger",
    "CSVFileQueryLogger"
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


LogRecord = namedtuple("LogRecord", ["timestamp", "query", "cube", "cell",
                                     "identity" "elapsed_time"])


def create_query_logger(type_, *args, **kwargs):
    """Gets a new instance of a query logger."""

    ns = get_namespace("query_loggers")
    if not ns:
        ns = initialize_namespace("query_loggers", root_class=QueryLogger,
                                  suffix="_query_logger",
                                  option_checking=True)
    try:
        factory = ns[type_]
    except KeyError:
        raise ConfigurationError("Unknown query logger '%s'" % type_)

    return factory(*args, **kwargs)


class QueryLogger(object):
    @contextmanager
    def log_time(self, query, browser, cell, identity=None):
        start = time.time()
        yield
        elapsed = time.time() - start
        self.log(query, browser, cell, identity, elapsed)

    def log(self, query, browser, cell, identity=None, elapsed=None):
        row = LogRecord(time.time(),
               query,
               browser.cube.name,
               str(cell),
               identity,
               elapsed or 0
               )

        self.write_log(log)


class DefaultQueryLogger(QueryLogger):
    def __init__(self, logger=None, **options):
        self.logger = logger

    def write_record(self, record):
        cell_str = "'%s'" % str(record.cell) if record.cell else "none"
        identity_str = "'%s'" % str(record.identity) if record.identity else "none"
        self.logger.info("query: %s cube: %s cell: %s identity: %s time: %s"
                         % (record.query, record.cube, cell_str, identity_str,
                            record.elapsed))


class CSVFileQueryLogger(QueryLogger):
    def __init__(self, path=None, **options):
        self.path = path

    def write_record(self, record):
        with io.open(path, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(record)

