# -*- coding=utf -*-
from contextlib import contextmanager
from collections import namedtuple
from threading import Thread
from Queue import Queue

import datetime
import time
import csv
import io

from ..extensions import extensions, Extensible
from ..logging import get_logger
from ..errors import *

__all__ = [
    "create_request_log_handler",
    "configured_request_log_handlers",

    "RequestLogger",
    "AsyncRequestLogger",
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
                handler = extensions.request_log_handler("default", logger)
            else:
                handler = extensions.request_log_handler(type_, **options)

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
            "cube": browser.cube,
            "identity": identity,
            "elapsed_time": elapsed or 0,
            "cell": cell
        }
        record.update(other)

        record = self._stringify_record(record)

        for handler in self.handlers:
            handler.write_record(browser.cube, cell, record)


    def _stringify_record(self, record):
        """Return a log rectord with object attributes converted to strings"""
        record = dict(record)

        record["cube"] = str(record["cube"])

        cell = record.get("cell")
        record["cell"] = str(cell) if cell is not None else None

        split = record.get("split")
        record["split"] = str(split) if split is not None else None

        return record


class AsyncRequestLogger(RequestLogger):
    def __init__(self, handlers=None):
        super(AsyncRequestLogger, self).__init__(handlers)
        self.queue = Queue()
        self.thread = Thread(target=self.log_consumer,
                              name="slicer_logging")
        self.thread.daemon = True
        self.thread.start()

    def log(self, *args, **kwargs):
        self.queue.put( (args, kwargs) )

    def log_consumer(self):
        while True:
            (args, kwargs) = self.queue.get()
            super(AsyncRequestLogger, self).log(*args, **kwargs)

class RequestLogHandler(Extensible):
    def write_record(self, record):
        pass


class DefaultRequestLogHandler(RequestLogHandler):
    def __init__(self, logger=None, **options):
        self.logger = logger

    def write_record(self, cube, cell, record, **options):
        if cell:
            cell_str = "'%s'" % str(cell)
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

    def write_record(self, cube, cell, record):
        out = []

        for key in REQUEST_LOG_ITEMS:
            item = record.get(key)
            if item is not None:
                item = unicode(item)
            out.append(item)

        with io.open(self.path, 'ab') as f:
            writer = csv.writer(f)
            writer.writerow(out)

