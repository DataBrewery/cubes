import unittest
from sqlalchemy import create_engine, MetaData, Table, Integer, String, Column
from cubes import *
from ...common import CubesTestCaseBase

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
                    (1, 20130901,  10),
                    (2, 20130902,  20),
                    (3, 20130903,  40),
                    (4, 20130910,  80),
                    (5, 20130915, 160),
                ]

        for row in data:
            insert = self.facts.insert().values(data)
            engine.execute(insert)

        for day in range(1, 30):
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

    def test_empty(self):
        browser = self.workspace.browser("facts")
        result = browser.aggregate()

        self.assertEqual(1550, result.summary["amount_sum"])

    def test_cell_count(self):
        drilldown = [("date", "default", "day")]

        browser = self.workspace.browser("facts")
        result = browser.aggregate(drilldown=drilldown)
        self.assertEqual(5, result.total_cell_count)

        browser = self.workspace.browser("facts_master")
        result = browser.aggregate(drilldown=drilldown)
        self.assertEqual(5, result.total_cell_count)

        browser = self.workspace.browser("facts_detail")
        result = browser.aggregate(drilldown=drilldown)
        self.assertEqual(5, result.total_cell_count)

    def test_drilldown(self):
        browser = self.workspace.browser("facts_master")
        result = browser.aggregate(drilldown=[("date", "default", "day")])

        self.assertEqual(5, result.total_cell_count)

