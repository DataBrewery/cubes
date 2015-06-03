# -*- coding: utf-8 -*-
from contextlib import contextmanager
from collections import namedtuple
from threading import Thread

import datetime
import time
import csv
import io
import json

from .. import ext
from .. import compat
from ..logging import get_logger
from ..errors import *
from ..browser import Drilldown

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
                handler = ext.request_log_handler("default", logger)
            else:
                handler = ext.request_log_handler(type_, **options)

            handlers.append(handler)

    return handlers


class RequestLogger(object):
    def __init__(self, handlers=None):
        if handlers:
            self.handlers = list(handlers)
        else:
            self.handlers = []

        self.logger = get_logger()

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
            try:
                handler.write_record(browser.cube, cell, record)
            except Exception as e:
                self.logger.error("Server log handler error (%s): %s"
                                  % (type(handler).__name__, str(e)))


    def _stringify_record(self, record):
        """Return a log rectord with object attributes converted to unicode strings"""
        record = dict(record)

        record["cube"] = compat.text_type(record["cube"])

        cell = record.get("cell")
        record["cell"] = compat.text_type(cell) if cell is not None else None

        split = record.get("split")
        record["split"] = compat.text_type(split) if split is not None else None

        return record


class AsyncRequestLogger(RequestLogger):
    def __init__(self, handlers=None):
        super(AsyncRequestLogger, self).__init__(handlers)
        self.queue = compat.Queue()
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

class RequestLogHandler(object):
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
                item = compat.text_type(item)
            out.append(item)

        with io.open(self.path, 'ab') as f:
            writer = csv.writer(f)
            writer.writerow(out)

class JSONRequestLogHandler(RequestLogHandler):
    def __init__(self, path=None, **options):
        """Creates a JSON logger which logs requests in a JSON lines. It
        includes two lists: `cell_dimensions` and `drilldown_dimensions`."""
        self.path = path

    def write_record(self, cube, cell, record):
        out = []

        drilldown = record.get("drilldown")

        if drilldown is not None:
            if cell:
                drilldown = Drilldown(drilldown, cell)
                record["drilldown"] = str(drilldown)
            else:
                drilldown = []
                record["drilldown"] = None

        record["timestamp"] = record["timestamp"].isoformat()
        # Collect dimension uses
        uses = []

        cuts = cell.cuts if cell else []

        for cut in cuts:
            dim = cube.dimension(cut.dimension)
            depth = cut.level_depth()
            if depth:
                level = dim.hierarchy(cut.hierarchy)[depth-1]
                level_name = str(level)
            else:
                level_name = None

            use = {
                "dimension": str(dim),
                "hierarchy": str(cut.hierarchy),
                "level": str(level_name),
                "value": str(cut)
            }
            uses.append(use)

        record["cell_dimensions"] = uses

        uses = []

        for item in drilldown or []:
            (dim, hier, levels) = item[0:3]
            if levels:
                level = str(levels[-1])
            else:
                level = None

            use = {
                "dimension": str(dim),
                "hierarchy": str(hier),
                "level": str(level),
                "value": None
            }
            uses.append(use)

        record["drilldown_dimensions"] = uses
        line = json.dumps(record)

        with io.open(self.path, 'ab') as f:
            json.dump(record, f)
            f.write("\n")

