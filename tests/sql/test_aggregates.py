# -*- coding=utf -*-
import unittest
from sqlalchemy import create_engine, MetaData, Table, Integer, String, Column
from cubes import *
from cubes.errors import *
from ..common import CubesTestCaseBase

from json import dumps

def printable(obj):
    return dumps(obj, indent=4)

class AggregatesTestCase(CubesTestCaseBase):
    sql_engine = "sqlite:///"

    def setUp(self):
        super(AggregatesTestCase, self).setUp()

        self.facts = Table("facts", self.metadata,
                        Column("id", Integer),
                        Column("year", Integer),
                        Column("amount", Integer),
                        Column("price", Integer),
                        Column("discount", Integer)
                        )
        self.metadata.create_all()

        data = [
            ( 1, 2010, 1, 100,  0),
            ( 2, 2010, 2, 200, 10),
            ( 3, 2010, 4, 300,  0),
            ( 4, 2010, 8, 400, 20),
            ( 5, 2011, 1, 500,  0),
            ( 6, 2011, 2, 600, 40),
            ( 7, 2011, 4, 700,  0),
            ( 8, 2011, 8, 800, 80),
            ( 9, 2012, 1, 100,  0),
            (10, 2012, 2, 200,  0),
            (11, 2012, 4, 300,  0),
            (12, 2012, 8, 400, 10),
            (13, 2013, 1, 500,  0),
            (14, 2013, 2, 600,  0),
            (15, 2013, 4, 700,  0),
            (16, 2013, 8, 800, 20),
        ]

        self.load_data(self.facts, data)
        self.workspace = self.create_workspace(model="aggregates.json")

    def test_unknown_function(self):
        browser = self.workspace.browser("unknown_function")

        with self.assertRaisesRegex(ArgumentError, "Unknown.*function"):
            browser.aggregate()

    def test_explicit(self):
        browser = self.workspace.browser("default")
        result = browser.aggregate()
        summary = result.summary
        self.assertEqual(60, summary["amount_sum"])
        self.assertEqual(16, summary["count"])

    def test_post_calculation(self):
        browser = self.workspace.browser("postcalc_in_measure")

        result = browser.aggregate(drilldown=["year"])
        cells = list(result.cells)
        aggregates = sorted(cells[0].keys())
        self.assertSequenceEqual(['amount_sma', 'amount_sum', 'count', 'year'],
                                 aggregates)
