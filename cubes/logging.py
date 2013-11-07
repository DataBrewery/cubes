# -*- coding=utf -*-

from __future__ import absolute_import

from logging import getLogger, Formatter, StreamHandler
from contextlib import contextmanager
from collections import namedtuple
import datetime
import time
import csv
import io

from .extensions import get_namespace, initialize_namespace
from .errors import *

__all__ = [
    "logger_name",
    "get_logger",
    "create_logger",

    "create_query_log_handler",
    "configured_query_log_handlers",

    "QueryLogger",
    "QueryLogHandler",
    "DefaultQueryLogHandler",
    "CSVFileQueryLogHandler"
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
                                     "identity", "elapsed_time"])


def create_query_log_handler(type_, *args, **kwargs):
    """Gets a new instance of a query logger."""

    ns = get_namespace("query_log_handlers")
    if not ns:
        ns = initialize_namespace("query_log_hanlers",
                                  root_class=QueryLogHandler,
                                  suffix="_query_log_handler",
                                  option_checking=True)
    try:
        factory = ns[type_]
    except KeyError:
        raise ConfigurationError("Unknown query log handler '%s'" % type_)

    return factory(*args, **kwargs)


def configured_query_log_handlers(config, prefix="query_log",
                                  default_logger=None):
    """Returns configured query loggers as defined in the `config`."""

    handlers = []

    for section in config.sections():
        if section.startswith(prefix):
            options = dict(config.items(section))
            type_ = options.pop("type")
            if type_ == "default":
                logger = default_logger or get_logger()
                handler = create_query_log_handler("default", logger)
            else:
                handler = create_query_log_handler(type_, **options)

            handlers.append(handler)

    return handlers


class QueryLogger(object):
    def __init__(self, handlers=None):
        if handlers:
            self.handlers = list(handlers)
        else:
            self.handlers = []

    @contextmanager
    def log_time(self, query, browser, cell, identity=None):
        start = time.time()
        yield
        elapsed = time.time() - start
        self.log(query, browser, cell, identity, elapsed)

    def log(self, query, browser, cell, identity=None, elapsed=None):
        cell_string = str(cell) if cell is not None else None

        record = LogRecord(datetime.datetime.now(),
                           query,
                           browser.cube.name,
                           cell_string,
                           identity,
                           elapsed or 0)

        for handler in self.handlers:
            handler.write_record(record)


class QueryLogHandler(object):
    pass


class DefaultQueryLogHandler(QueryLogHandler):
    def __init__(self, logger=None, **options):
        self.logger = logger

    def write_record(self, record):
        cell_str = "'%s'" % str(record.cell) if record.cell is not None else "none"
        identity_str = "'%s'" % str(record.identity) if record.identity else "none"
        self.logger.info("query:%s cube:%s cell:%s identity:%s time:%s"
                         % (record.query, record.cube, cell_str, identity_str,
                            record.elapsed_time))


class CSVFileQueryLogHandler(QueryLogHandler):
    def __init__(self, path=None, **options):
        self.path = path

    def write_record(self, record):
        out = []
        for item in record:
            if item is not None:
                item = unicode(item)
            out.append(item)

        with io.open(self.path, 'ab') as f:
            writer = csv.writer(f)
            writer.writerow(out)

