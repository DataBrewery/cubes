# -*- encoding: utf-8 -*-
from __future__ import absolute_import

from unittest import TestCase, skip
import os
import json
import re
import sqlalchemy as sa
import datetime

from cubes import create_dimension, create_cube

from .common import create_table, SQLTestCase

from cubes.errors import HierarchyError
from cubes.browser import PointCut, SetCut, RangeCut, Cell
from cubes.sql import SQLBrowser, SQLStore

from .dw.demo import create_demo_dw, TinyDemoModelProvider
#
# TODO: this should be workspace-free test
#

CONNECTION = "sqlite://"

class SQLBrowserTestCase(SQLTestCase):
    @classmethod
    def setUpClass(self):
        self.dw = create_demo_dw(CONNECTION, None, False)
        self.store = SQLStore(engine=self.dw.engine,
                              metadata=self.dw.md)

        self.provider = TinyDemoModelProvider()
        naming = {
            "fact_prefix": "fact_",
            "dimension_prefix": "dim_"
        }

        self.browser = SQLBrowser(self.provider.cube("sales"),
                                  store=self.store,
                                  **naming)

    # Helper methods
    def cube(self, name):
        return self.provider.cube(name)

    def dimension(self, name):
        return self.provider.dimension(name)

    def table(self, name):
        return self.dw.table(name)

    def execute(self, *args, **kwargs):
        return self.dw.engine.execute(*args, **kwargs)

# class SQLValidateTestCase(SQLBrowserTestCase):
#    def test_basic(self):
#        self.store.validate(cube)

class SQLStatementsTestCase(SQLBrowserTestCase):
    """"Test basic SQL statement generation in the browser."""
    def setUp(self):
        super(SQLStatementsTestCase, self).setUp()

        self.view = self.browser.star.star(self.browser.base_columns)

    def test_attribute_column(self):
        """Test proper selection of attribute column."""
        # Test columns with physical rep
        cube = self.cube("sales")
        dim_item = self.table("dim_item")
        dim_category = self.table("dim_category")

        attr = self.dimension("item").attribute("name")
        import pdb; pdb.set_trace()
        self.assertColumnEqual(self.browser.attribute_column(attr),
                               dim_item.columns["name"])

        attr = self.dimension("category").attribute("name")
        self.assertColumnEqual(self.browser.attribute_column(attr),
                               dim_category.columns["name"])

        # TODO: Test derived column
class SQLAggregateTestCase(SQLBrowserTestCase):
    def setUp(self):
        super(self, SQLAggregateTestCase).setUp(self)

    def test_aggregate_base(self):
        """Aggregate all aggregates without any cell and no drilldown"""

    def test_aggregate_point(self):
        """Aggregate with point cut"""

    def test_aggregate_set(self):
        """Aggregate with set cut"""

    def test_aggregate_range(self):
        """Aggregate with range cut"""

    def test_aggregate_multiple(self):
        """Aggregate with multiple cuts"""

    def test_aggregate_negative(self):
        """Aggregate with negative cut (point, set, range)"""

    def test_drilldown(self):
        """Test basic drilldown"""
        # Test 1 dimension, no cell
        # Test 2-3 dimensions

    def test_drilldown_implicit(self):
        """Test implicit level from drilldown and cell"""

    def test_drilldown_explicit(self):
        """Test drilldown with explicit hierarchy level"""


