# -*- coding=utf -*-

import urllib2
import json
import logging
import urllib
from ...common import get_logger
from ...browser import *

class SlicerBrowser(AggregationBrowser):
    """Aggregation browser for Cubes Slicer OLAP server."""

    def __init__(self, cube, store, locale=None, **options):
        """Browser for another Slicer server.
        """
        super(SlicerBrowser, self).__init__(cube, store, locale)

        self.logger = get_logger()
        self.cube = cube
        self.locale = locale
        self.store = store

    def features(self):

        features = {
            "actions": ["aggregate", "facts"],
        }

        return features

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
            params["order"] = self._order_param(order)

        if page is not None:
            params["page"] = str(page)

        if page_size is not None:
            params["page_size"] = str(page_size)


        response = self.store.cube_request("aggregate",
                                           self.cube.name, params)

        result = AggregationResult()

        result.cells = response.get('cells', [])

        if "summary" in response:
            result.summary = response.get('summary')

        result.levels = response.get('levels', {})
        result.labels = response.get('labels', [])
        result.cell = cell
        result.aggregates = response.get('aggregates', [])

        return result

    def facts(self, cell=None, fields=None, order=None, page=None,
              page_size=None):

        cell = cell or Cell(self.cube)
        if fields:
            attributes = self.cube.get_attributes(fields)
        else:
            attributes = []

        order = self.prepare_order(order, is_aggregate=False)

        params = {}

        if cell:
            params["cut"] = string_from_cuts(cell.cuts)

        if order:
            params["order"] = self._order_param(order)

        if page is not None:
            params["page"] = str(page)

        if page_size is not None:
            params["page_size"] = str(page_size)

        if attributes:
            params["fields"] = ",".join(str(attr) for attr in attributes)

        params["format"] = "json_lines"

        response = self.store.cube_request("facts", self.cube.name, params,
                                           is_lines=True)

        return Facts(response, attributes)

    def _order_param(self, order):
        """Prepare an order string in form: ``attribute:direction``"""
        string = ",".join("%s:%s" % (o[0], o[1]) for o in order)
        return string

    def fact(self, key):
        raise NotImplementedError

