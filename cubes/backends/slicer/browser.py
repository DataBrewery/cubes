# -*- coding=utf -*-

import urllib2
import json
import logging
import urllib
from ...browser import *
from ...common import get_logger

class SlicerBrowser(AggregationBrowser):
    """Aggregation browser for Cubes Slicer OLAP server."""

    def __init__(self, cube, store, locale=None, **options):
        """Demo backend browser. This backend is serves just as example of a
        backend. Uses another Slicer server instance for doing all the work.
        You might use it as a template for your own browser.

        Attributes:

        * `cube` – obligatory, but currently unused here
        * `url` - base url of Cubes Slicer OLAP server

        """
        super(SlicerBrowser, self).__init__(cube, store, locale)

        self.logger = get_logger()
        self.cube = cube
        self.locale = locale
        self.store = store

    def _dditem_to_string(self, dditem):
        s = dditem.dimension.name
        if dditem.hierarchy:
            s += "@" + dditem.hierarchy.name
        if len(dditem.levels):
            s += ":" + dditem.levels[-1].name
        return s

    def aggregate(self, cell=None, aggregates=None, drilldown=None,
                  split=None, page=None, page_size=None, order=None):

        params = {}
        cell = cell or Cell(self.cube)

        if cell:
            params["cut"] = string_from_cuts(cell.cuts)

        if drilldown:
            drilldown = Drilldown(drilldown, cell)
            params["drilldown"] = ",".join(drilldown.items_as_strings())

        if split:
            params["split"] = str(split)

        if aggregates:
            names = [a.name for a in aggregates]
            params["aggregates"] = ",".join(names)

        if order:
            params["order"] = str(order)

        if page is not None:
            params["page"] = str(page)

        if page_size is not None:
            params["page_size"] = str(page_size)


        reply = self.store.cube_request("aggregate", self.cube.name, **params)

        result = AggregationResult()

        result.cells = reply.get('cells', [])

        if "summary" in reply:
            result.summary = reply.get('summary')

        result.levels = reply.get('levels', {})
        result.labels = reply.get('labels', [])
        result.cell = cell
        result.aggregates = reply.get('aggregates', [])

        return result

    def facts(self, cell, **options):
        # TODO: This would be much better with CSV - we are missing data types
        raise NotImplementedError

    def fact(self, key):
        raise NotImplementedError

