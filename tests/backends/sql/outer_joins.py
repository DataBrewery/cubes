# -*- coding=utf -*-
import unittest
from sqlalchemy import create_engine, MetaData, Table, Integer, String, Column
from cubes import *
from ...common import CubesTestCaseBase

from json import dumps

def printable(obj):
    return dumps(obj, indent=4)

class OuterJoinsTestCase(CubesTestCaseBase):
    def setUp(self):
        super(OuterJoinsTestCase, self).setUp()

        engine = create_engine("sqlite:///")
        metadata = MetaData(bind=engine)

        self.facts = Table("facts", metadata,
                        Column("id", Integer),
                        Column("id_date", Integer),
                        Column("amount", Integer)
                        )
        self.dim_date = Table("dim_date", metadata,
                        Column("id", Integer),
                        Column("year", Integer),
                        Column("month", Integer),
                        Column("day", Integer)
                        )
        metadata.create_all()

        data = [
                    (1, 20130901,   10),
                    (2, 20130902,   20),
                    (3, 20130903,   40),
                    (4, 20130910,   80),
                    (5, 20130915,  160),
                    (6, 20131001,  320),
                    (7, 20131002,  640),
                    (8, 20131004, 1280),
                ]

        for row in data:
            insert = self.facts.insert().values(data)
            engine.execute(insert)

        for day in range(1, 31):
            row = (20130900+day, 2013, 9, day)
            insert = self.dim_date.insert().values(row)
            engine.execute(insert)

        self.workspace = Workspace()
        self.workspace.register_default_store("sql", engine=engine,
                dimension_prefix="dim_")

        self.workspace.add_model(self.model_path("outer_joins.json"))
        self.cube = self.workspace.cube("facts")
        self.cube_master = self.workspace.cube("facts_master")
        self.cube_detail = self.workspace.cube("facts_detail")

        # FIXME: remove this once we are happy
        self.workspace.logger.setLevel("DEBUG")
        self.workspace.logger.info("=== test setup")

        self.logger = self.workspace.logger
        self.day_drilldown = [("date", "default", "day")]
        self.month_drilldown = [("date", "default", "month")]
        self.year_drilldown = [("date", "default", "year")]

    def test_empty(self):
        browser = self.workspace.browser("facts")
        result = browser.aggregate()

        self.assertEqual(20400, result.summary["amount_sum"])

    def test_cell_count_match(self):

        browser = self.workspace.browser("facts")
        result = browser.aggregate(drilldown=self.day_drilldown)
        self.assertEqual(5, len(list(result.cells)))

        result = browser.aggregate(drilldown=self.month_drilldown)
        cells = list(result.cells)
        self.assertEqual(1, len(cells))

    def test_cell_count_master(self):
        browser = self.workspace.browser("facts_master")

        # All results should be +1 compared to "match" – all unknown dates

        result = browser.aggregate(drilldown=self.day_drilldown)
        self.assertEqual(20400, result.summary["amount_sum"])
        cells = list(result.cells)
        self.assertEqual(6, len(cells))

        result = browser.aggregate(drilldown=self.month_drilldown)
        cells = list(result.cells)
        self.assertEqual(2, len(cells))

    def test_cell_count_detail(self):
        browser = self.workspace.browser("facts_detail")

        result = browser.aggregate(drilldown=self.day_drilldown)
        self.assertEqual(20400, result.summary["amount_sum"])
        cells = list(result.cells)
        self.assertEqual(30, len(cells))

        result = browser.aggregate(drilldown=self.month_drilldown)
        cells = list(result.cells)
        self.assertEqual(2, len(cells))

