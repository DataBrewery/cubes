# -*- coding=utf -*-
import unittest
from sqlalchemy import create_engine, MetaData, Table, Integer, String, Column
from cubes import *
from ...common import CubesTestCaseBase

from json import dumps

def printable(obj):
    return dumps(obj, indent=4)

class JoinsTestCase(CubesTestCaseBase):
    sql_engine = "sqlite:///"

    def setUp(self):
        super(JoinsTestCase, self).setUp()

        self.facts = Table("facts", self.metadata,
                        Column("id", Integer),
                        Column("id_date", Integer),
                        Column("id_city", Integer),
                        Column("amount", Integer)
                        )
        self.dim_date = Table("dim_date", self.metadata,
                        Column("id", Integer),
                        Column("year", Integer),
                        Column("month", Integer),
                        Column("day", Integer)
                        )
        self.dim_city = Table("dim_city", self.metadata,
                        Column("id", Integer),
                        Column("name", Integer),
                        Column("country_code", Integer)
                        )
        self.dim_country = Table("dim_country", self.metadata,
                        Column("code", String),
                        Column("name", Integer)
                        )
        self.metadata.create_all()

        data = [
                    (1, 20130901, 1,  10),
                    (2, 20130902, 1,  20),
                    (3, 20130903, 2,  40),
                    (4, 20130910, 2,  80),
                    (5, 20130915, 1, 160),
                    (6, 20131001, 1, 320),
                    (7, 20131002, 2, 640),
                    (8, 20131004, 2, 1280),
                ]

        self.load_data(self.facts, data)

        data = [
                    (1, "Bratislava", "sk"),
                    (2, "New York", "us")
                ]

        self.load_data(self.dim_city, data)

        data = [
                    ("sk", "Slovakia"),
                    ("us", "United States")
                ]

        self.load_data(self.dim_city, data)

        data = []
        for day in range(1, 31):
            row = (20130900+day, 2013, 9, day)
            data.append(row)

        self.load_data(self.dim_date, data)

        self.workspace = Workspace()
        self.workspace.register_default_store("sql", engine=self.engine,
                dimension_prefix="dim_")

        self.workspace.add_model(self.model_path("joins.json"))
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
        self.city_drilldown = [("city")]

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
        self.assertEqual(1, len(cells))

    def test_three_tables(self):
        browser = self.workspace.browser("threetables")
        result = browser.aggregate(drilldown=self.day_drilldown)
        self.assertEqual(20400, result.summary["amount_sum"])

        result = browser.aggregate(drilldown=
                                    self.city_drilldown+self.year_drilldown)
        cells = list(result.cells)
        self.assertEqual(20400, result.summary["amount_sum"])

