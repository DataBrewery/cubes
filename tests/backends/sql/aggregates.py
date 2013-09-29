# -*- coding=utf -*-
import unittest
from sqlalchemy import create_engine, MetaData, Table, Integer, String, Column
from cubes import *
from ...common import CubesTestCaseBase

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
            ( 1, 2010,    1, 100,  0),
            ( 2, 2010,    2, 200, 10),
            ( 3, 2010,    4, 300,  0),
            ( 4, 2010,    8, 400, 20),
            ( 5, 2010,   16, 500,  0),
            ( 6, 2010,   32, 600, 40),
            ( 7, 2010,   64, 700,  0),
            ( 8, 2010,  128, 800, 80),
            ( 9, 2011,    1, 100,  0),
            (10, 2011,    2, 200,  0),
            (11, 2011,    4, 300,  0),
            (12, 2011,    8, 400, 10),
            (13, 2011,   16, 500,  0),
            (14, 2011,   32, 600,  0),
            (15, 2011,   64, 700,  0),
            (16, 2011,  128, 800, 20),
        ]

        self.load_data(self.facts, data)
        self.workspace = self.create_workspace(model="aggregates.json")

        self.workspace.logger.setLevel("DEBUG")

    def test_validate_model(self):
        self.cube = self.workspace.cube("implicit_aggregates")
        aggregates = [a.name for a in self.cube.aggregates]
        self.assertSequenceEqual(["amount_sum",
                                  "amount_min",
                                  "amount_max",
                                  "amount_wma",
                                  "price_sum",
                                  "discount_sum"
                                  ],
                                  aggregates)
    def test_explicit(self):
        browser = self.workspace.browser("explicit_aggregates")
        result = browser.aggregate()
        summary = result.summary
        self.assertEqual(510, summary["amount_sum"])
        self.assertEqual(16, summary["count"])
