# -*- encoding: utf-8 -*-
from __future__ import absolute_import

from unittest import TestCase, skip
import os
import json
import re
import sqlalchemy as sa
import datetime

from .common import create_table, SQLTestCase

from cubes.errors import HierarchyError
from cubes.cells import PointCut, SetCut, RangeCut, Cell
from cubes.sql import SQLBrowser, SQLStore
from cubes.sql.query import FACT_KEY_LABEL

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

        base = base_attributes(self.browser.cube.all_attributes)
        base = [attr.ref for attr in base]
        self.view = self.browser.star.get_star(base)

    def select(self, attrs, whereclause=None):
        """Returns a select statement from the star view"""
        columns = [self.browser.star.column(attr) for attr in attrs]

        return sa.select(columns,
                         from_obj=self.view,
                         whereclause=whereclause)

    def test_attribute_column(self):
        """Test proper selection of attribute column."""
        # Test columns with physical rep
        cube = self.cube("sales")
        dim_item = self.table("dim_item")
        dim_category = self.table("dim_category")

        attr = self.dimension("item").attribute("name")
        self.assertColumnEqual(self.browser.attribute_column(attr),
                               dim_item.columns["name"])

        attr = self.dimension("category").attribute("name")
        self.assertColumnEqual(self.browser.attribute_column(attr),
                               dim_category.columns["name"])

        # TODO: Test derived column
    def test_condition_for_point(self):
        condition = self.browser.condition_for_point(self.dimension("item"),
                                                     ["1"])

        select = self.select([FACT_KEY_LABEL], condition)
        keys = [row[FACT_KEY_LABEL] for row in self.execute(select)]

        table = self.table("fact_sales")
        select = table.select().where(table.columns["item_key"] == 1)
        raw_keys = [row["id"] for row in self.execute(select)]

        self.assertEqual(len(keys), len(raw_keys))
        self.assertCountEqual(keys, raw_keys)

    def test_condition_for_hierarchy_point(self):
        # Test multi-level point
        #
        # Note:
        # This test requires that there is only one item for 2015-01-01
        # See data in DW demo
        condition = self.browser.condition_for_point(self.dimension("date"),
                                                     [2015,1,1])

        select = self.select([FACT_KEY_LABEL], condition)
        keys = [row[FACT_KEY_LABEL] for row in self.execute(select)]

        table = self.table("fact_sales")
        select = table.select().where(table.columns["date_key"] == 20150101)
        raw_keys = [row["id"] for row in self.execute(select)]

        self.assertEqual(len(keys), 1)
        self.assertEqual(len(keys), len(raw_keys))
        self.assertCountEqual(keys, raw_keys)

    @skip("Test missing")
    def test_range_condition(self):
        """"Test Browser.range_condition"""
        # Test single level paths
        # Test multi-level paths
        # Test uneven paths
        # Test lower bound only
        # Test upper bound only

@skip("Tests missing")
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


