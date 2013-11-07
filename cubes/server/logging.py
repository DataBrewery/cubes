# -*- coding=utf -*-
from contextlib import contextmanager
from collections import namedtuple

import datetime
import time
import csv
import io

from ..extensions import get_namespace, initialize_namespace
from ..logging import get_logger
from ..errors import *

__all__ = [
    "create_request_log_handler",
    "configured_request_log_handlers",

    "RequestLogger",
    "RequestLogHandler",
    "DefaultRequestLogHandler",
    "CSVFileRequestLogHandler",
    "QUERY_LOG_ITEMS"
]


REQUEST_LOG_ITEMS = [
    "timestamp",
    "method",
    "cube",
    "cell",
    "identity",
    "elapsed_time",
    "attributes",
    "split",
    "drilldown",
    "page",
    "page_size",
    "format",
    "headers"
]


def create_request_log_handler(type_, *args, **kwargs):
    """Gets a new instance of a query logger."""

    ns = get_namespace("request_log_handlers")
    if not ns:
        ns = initialize_namespace("request_log_handlers",
                                  root_class=RequestLogHandler,
                                  suffix="_request_log_handler",
                                  option_checking=True)
    try:
        factory = ns[type_]
    except KeyError:
        raise ConfigurationError("Unknown request log handler '%s'" % type_)

    return factory(*args, **kwargs)


def configured_request_log_handlers(config, prefix="query_log",
                                    default_logger=None):
    """Returns configured query loggers as defined in the `config`."""

    handlers = []

    for section in config.sections():
        if section.startswith(prefix):
            options = dict(config.items(section))
            type_ = options.pop("type")
            if type_ == "default":
                logger = default_logger or get_logger()
                handler = create_request_log_handler("default", logger)
            else:
                handler = create_request_log_handler(type_, **options)

            handlers.append(handler)

    return handlers


class RequestLogger(object):
    def __init__(self, handlers=None):
        if handlers:
            self.handlers = list(handlers)
        else:
            self.handlers = []

    @contextmanager
    def log_time(self, method, browser, cell, identity=None, **other):
        start = time.time()
        yield
        elapsed = time.time() - start
        self.log(method, browser, cell, identity, elapsed, **other)

    def log(self, method, browser, cell, identity=None, elapsed=None, **other):

        record = {
            "timestamp": datetime.datetime.now(),
            "method": method,
            "cube": browser.cube.name,
            "identity": identity,
            "elapsed_time": elapsed or 0
        }
        record.update(other)

        record["cell"] = str(cell) if cell is not None else None

        if "split" in record and record["split"] is not None:
            record["split"] = str(record["split"])

        for handler in self.handlers:
            handler.write_record(record)


class RequestLogHandler(object):
    def write_record(self, record):
        pass


class DefaultRequestLogHandler(RequestLogHandler):
    def __init__(self, logger=None, **options):
        self.logger = logger

    def write_record(self, record):
        if record.get("cell"):
            cell_str = "'%s'" % record["cell"]
        else:
            cell_str = "none"

        if record.get("identity"):
            identity_str = "'%s'" % str(record["identity"])
        else:
            identity_str = "none"

        self.logger.info("method:%s cube:%s cell:%s identity:%s time:%s"
                         % (record["method"], record["cube"], cell_str,
                            identity_str, record["elapsed_time"]))


class CSVFileRequestLogHandler(RequestLogHandler):
    def __init__(self, path=None, **options):
        self.path = path

    def write_record(self, record):
        out = []

        for key in REQUEST_LOG_ITEMS:
            item = record.get(key)
            if item is not None:
                item = unicode(item)
            out.append(item)

        with io.open(self.path, 'ab') as f:
            writer = csv.writer(f)
            writer.writerow(out)

