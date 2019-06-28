# -*- coding=utf -*-

import json
import logging

from ..query.browser import BrowserFeatures, BrowserFeatureAction
from ..logging import get_logger
from ..query import *
from ..query.result import AggregationResult, Facts


class SlicerBrowser(AggregationBrowser, name="slicer"):
    """Aggregation browser for Cubes Slicer OLAP server."""

    def __init__(self, cube, store, locale=None, **options):
        """Browser for another Slicer server.
        """
        super().__init__(cube, store, locale)

        self.logger = get_logger()
        self.cube = cube
        self.locale = locale
        self.store = store

    def features(self) -> BrowserFeatures:

        # Get the original features as provided by the Slicer server.
        # They are stored in browser_options in the Slicer model provider's
        # cube().
        cube_features = dict(self.cube.browser_options.get("features", {}))

        # Replace only the actions, as we are not just a simple proxy.
        features = BrowserFeatures(
            actions=[
                BrowserFeatureAction.aggregate,
                BrowserFeatureAction.facts,
                BrowserFeatureAction.fact,
                BrowserFeatureAction.cell,
                BrowserFeatureAction.members,
            ],
            aggregate_functions=cube_features.get('aggregate_functions'),
            post_aggregate_functions=cube_features.get('post_aggregate_functions')
        )

        return features

    def provide_aggregate(self, cell, aggregates, drilldown, split, order,
                          page, page_size, **options):

        params = {}

        if cell:
            params["cut"] = string_from_cuts(cell.cuts)

        if drilldown:
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
                                           self.cube.basename, params)

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

        cell = cell or Cell()
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

        response = self.store.cube_request("facts", self.cube.basename, params,
                                           is_lines=True)

        return Facts(response, attributes)

    def provide_members(self, cell=None, dimension=None, levels=None,
                        hierarchy=None, attributes=None, page=None,
                        page_size=None, order=None, **options):

        params = {}

        if cell:
            params["cut"] = string_from_cuts(cell.cuts)

        if order:
            params["order"] = self._order_param(order)

        if levels:
            params["level"] = str(levels[-1])

        if hierarchy:
            params["hierarchy"] = str(hierarchy)

        if page is not None:
            params["page"] = str(page)

        if page_size is not None:
            params["page_size"] = str(page_size)

        if attributes:
            params["fields"] = ",".join(str(attr) for attr in attributes)

        params["format"] = "json_lines"

        action = "/cube/{}/members/{}".format(self.cube.basename, str(dimension))
        response = self.store.request(action, params, is_lines=True)

        return response

    def cell_details(self, cell, dimension=None):
        cell = cell or Cell()

        params = {}
        if cell:
            params["cut"] = string_from_cuts(cell.cuts)

        if dimension:
            params["dimension"] = str(dimension)

        response = self.store.cube_request("cell", self.cube.basename, params) 

        return response

    def fact(self, fact_id):
        action = "/cube/{}/fact/{}".format(self.cube.basename, str(fact_id))
        response = self.store.request(action)
        return response

    def is_builtin_function(self, name, aggregate):
        return True

    def _order_param(self, order):
        """Prepare an order string in form: ``attribute:direction``"""
        string = ",".join("{}:{}".format(o[0], o[1]) for o in order)
        return string

