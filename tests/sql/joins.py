# -*- coding=utf -*-
import unittest
from sqlalchemy import create_engine, MetaData, Table, Integer, String, Column
from cubes import *
from ...common import CubesTestCaseBase

from json import dumps

def printable(obj):
    return dumps(obj, indent=4)

class JoinsTestCaseBase(CubesTestCaseBase):
    sql_engine = "sqlite:///"

    def setUp(self):
        super(JoinsTestCaseBase, self).setUp()

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
                    # Master-detail Match
                    ( 1, 20130901, 1,   20),
                    ( 2, 20130902, 1,   20),
                    ( 3, 20130903, 1,   20),
                    ( 4, 20130910, 1,   20),
                    ( 5, 20130915, 1,   20),
                    #             --------
                    #             ∑    100
                    # No city dimension
                    ( 6, 20131001, 9,  200),
                    ( 7, 20131002, 9,  200),
                    ( 8, 20131004, 9,  200),
                    ( 9, 20131101, 7,  200),
                    (10, 20131201, 7,  200),
                    #             --------
                    #             ∑   1000
                    #             ========
                    #             ∑   1100

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

        self.load_data(self.dim_country, data)

        data = []
        for day in range(1, 31):
            row = (20130900+day, 2013, 9, day)
            data.append(row)

        self.load_data(self.dim_date, data)

        self.workspace = Workspace()
        self.workspace.register_default_store("sql", engine=self.engine,
                dimension_prefix="dim_")

        self.workspace.import_model(self.model_path("joins.json"))
        self.cube = self.workspace.cube("facts")


class JoinsTestCase(JoinsTestCaseBase):
    def setUp(self):
        super(JoinsTestCase, self).setUp()

        self.day_drilldown = [("date", "default", "day")]
        self.month_drilldown = [("date", "default", "month")]
        self.year_drilldown = [("date", "default", "year")]
        self.city_drilldown = [("city")]

    def test_empty(self):
        browser = self.workspace.browser("facts")
        result = browser.aggregate()

        self.assertEqual(1100, result.summary["amount_sum"])

    def aggregate_summary(self, cube, *args, **kwargs):
        browser = self.workspace.browser(cube)
        result = browser.aggregate(*args, **kwargs)
        return result.summary

    def aggregate_cells(self, cube, *args, **kwargs):
        browser = self.workspace.browser(cube)
        result = browser.aggregate(*args, **kwargs)
        return list(result.cells)

    def test_cell_count_match(self):
        cells = self.aggregate_cells("facts", drilldown=self.city_drilldown)

        self.assertEqual(1, len(cells))
        self.assertEqual(100, cells[0]["amount_sum"])
        self.assertEqual("Bratislava", cells[0]["city.name"])

    def test_cell_count_master(self):
        cells = self.aggregate_cells("facts_master", drilldown=self.city_drilldown)
        summary = self.aggregate_summary("facts_master", drilldown=self.city_drilldown)
        self.assertEqual(1100, summary["amount_sum"])

        cells = self.aggregate_cells("facts_master", drilldown=self.city_drilldown)

        self.assertEqual(2, len(cells))

        names = [cell["city.name"] for cell in cells]
        self.assertSequenceEqual([None, "Bratislava"], names)

        amounts = [cell["amount_sum"] for cell in cells]
        self.assertSequenceEqual([1000, 100], amounts)

    def test_cell_count_detail(self):
        summary = self.aggregate_summary("facts_detail_city",
                                         drilldown=self.city_drilldown)
        self.assertEqual(100, summary["amount_sum"])

        cells = self.aggregate_cells("facts_detail_city", drilldown=self.city_drilldown)

        self.assertEqual(2, len(cells))

        names = [cell["city.name"] for cell in cells]
        self.assertSequenceEqual(["Bratislava", "New York"], names)

        amounts = [cell["amount_sum"] for cell in cells]
        self.assertSequenceEqual([100, 0], amounts)

    def test_cell_count_detail_not_found(self):
        cube = self.workspace.cube("facts_detail_city")
        cell = Cell(cube, [PointCut("city", [2])])
        browser = self.workspace.browser(cube)
        result = browser.aggregate(cell, drilldown=[("city", None, "city")])
        cells = list(result.cells)

        # We have one cell – one city from dim (nothing from facts)
        self.assertEqual(1, len(cells))
        # ... however, we have no facts with that city. 
        self.assertEqual(0, result.summary["record_count"])
        # The summary should be coalesced to zero
        self.assertEqual(0, result.summary["amount_sum"])

        names = [cell["city.name"] for cell in cells]
        self.assertSequenceEqual(["New York"], names)

    def test_three_tables(self):
        summary = self.aggregate_summary("threetables",
                                         drilldown=self.city_drilldown)
        self.assertEqual(100, summary["amount_sum"])

        drilldown = self.city_drilldown+self.year_drilldown
        cells = self.aggregate_cells("threetables", drilldown=drilldown)
        self.assertEqual(1, len(cells))

    def test_condition_and_drilldown(self):
        cube = self.workspace.cube("condition_and_drilldown")
        cell = Cell(cube, [PointCut("city", [2])])
        dd = [("date", None, "day")]
        cells = self.aggregate_cells("condition_and_drilldown", cell=cell,
                                     drilldown=dd)

        # We want every day from the date table
        self.assertEqual(30, len(cells))

        self.assertIn("record_count", cells[0])
        self.assertIn("amount_sum", cells[0])
        self.assertIn("date.year", cells[0])
        self.assertIn("date.month", cells[0])
        self.assertIn("date.day", cells[0])
        self.assertNotIn("city.id", cells[0])

    def test_split(self):
        cube = self.workspace.cube("condition_and_drilldown")
        split = Cell(cube, [RangeCut("date", [2013, 9, 1],
                                             [2013, 9, 3])])
        cells = self.aggregate_cells("condition_and_drilldown",
                                     split=split)

        # We want every day from the date table
        self.assertEqual(2, len(cells))
        self.assertIn(SPLIT_DIMENSION_NAME, cells[0])

        # Both: master and detail split

        cube = self.workspace.cube("condition_and_drilldown")
        split = Cell(cube, [
                            RangeCut("date", [2013, 9, 1],
                                             [2013, 9, 3]),
                            PointCut("city", [1])
                           ])
        cells = self.aggregate_cells("condition_and_drilldown",
                                     split=split)

        # We want every day from the date table
        self.assertEqual(2, len(cells))
        self.assertIn(SPLIT_DIMENSION_NAME, cells[0])

@unittest.skip("not yet")
class JoinAggregateCompositionTestCase(JoinsTestCaseBase):
    def setUp(self):
        super(JoinAggregateCompositionTestCase, self).setUp()

        self.cube = self.workspace.cube("matchdetail")

        MD = [("date_master", "default", "day")]
        DD = [("date_detail", "default", "day")]

        MC = Cell(self.cube, [PointCut("city_master", [2])])
        DC = Cell(self.cube, [PointCut("city_detail", [2])])

        cases = [
            {
                "args": (None, None, None, None),
                "cells": 0
            },
            {
                "args": (  MD, None, None, None),
                "cells": 5
            },
            {
                "args": (None,   MC, None, None),
                "cells": 0
            },
            {
                "args": (  MD,   MC, None, None),
                "cells": 0
            },
            {
                "args": (None, None,   DD, None),
                "cells": 0
            },
            {
                "args": (  MD, None,   DD, None),
                "cells": 0
            },
            {
                "args": (None,   MC,   DD, None),
                "cells": 0
            },
            {
                "args": (  MD,   MC,   DD, None),
                "cells": 0
            },
            {
                "args": (None, None, None,   DC),
                "cells": 0
            },
            {
                "args": (  MD, None, None,   DC),
                "cells": 0
            },
            {
                "args": (None,   MC, None,   DC),
                "cells": 0
            },
            {
                "args": (  MD,   MC, None,   DC),
                "cells": 0
            },
            {
                "args": (None, None,   DD,   DC),
                "cells": 0
            },
            {
                "args": (  MD, None,   DD,   DC),
                "cells": 0
            },
            {
                "args": (None,   MC,   DD,   DC),
                "cells": 0
            },
            {
                "args": (  MD,   MC,   DD,   DC),
                "cells": 0
            }
        ]


    def test_all(self):
        pass
