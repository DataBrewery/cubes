from common import CubesTestCaseBase
from cubes.errors import *
from cubes.time import *
from cubes import time_hierarchy_elements
from datetime import datetime


class DateTimeTestCase(CubesTestCaseBase):
    def setUp(self):
        super(DateTimeTestCase,self).setUp()

        self.workspace = self.create_workspace(model="datetime.json")

    def test_empty(self):
        dim = self.workspace.dimension("default_date")

        self.assertEqual("date", dim.role)
        self.assertIsNone(dim.level("year").role)

    def test_implicit_roles(self):
        dim = self.workspace.dimension("default_date")

        elements = time_hierarchy_elements(dim.hierarchy("ymd"))
        self.assertSequenceEqual(["year", "month", "day"], elements)

    def test_explicit_roles(self):
        dim = self.workspace.dimension("explicit_date")

        elements = time_hierarchy_elements(dim.hierarchy("ymd"))
        self.assertSequenceEqual(["year", "month", "day"], elements)

    def test_no_roles(self):
        dim = self.workspace.dimension("invalid_date")

        with self.assertRaises(ArgumentError):
            time_hierarchy_elements(dim.hierarchy("ymd"))

    def test_time_path(self):
        date = datetime(2012, 12, 24)

        self.assertEqual([], time_path(date, []))
        self.assertEqual([2012], time_path(date, ["year"]))
        self.assertEqual([12, 24], time_path(date, ["month", "day"]))
        self.assertEqual([2012, 4], time_path(date, ["year", "quarter"]))

