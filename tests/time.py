from common import CubesTestCaseBase
from cubes.errors import *
<<<<<<< HEAD
from cubes.calendar import *
=======
from cubes.time import *
from cubes import time_hierarchy_elements
>>>>>>> Started new 'time' module
from datetime import datetime


class DateTimeTestCase(CubesTestCaseBase):
    def setUp(self):
        super(DateTimeTestCase,self).setUp()

        self.workspace = self.create_workspace(model="datetime.json")
<<<<<<< HEAD
        self.cal = Calendar()
=======
>>>>>>> Started new 'time' module

    def test_empty(self):
        dim = self.workspace.dimension("default_date")

        self.assertEqual("date", dim.role)
        self.assertIsNone(dim.level("year").role)

    def test_implicit_roles(self):
        dim = self.workspace.dimension("default_date")

<<<<<<< HEAD
        elements = calendar_hierarchy_units(dim.hierarchy("ymd"))
=======
        elements = time_hierarchy_elements(dim.hierarchy("ymd"))
>>>>>>> Started new 'time' module
        self.assertSequenceEqual(["year", "month", "day"], elements)

    def test_explicit_roles(self):
        dim = self.workspace.dimension("explicit_date")

<<<<<<< HEAD
        elements = calendar_hierarchy_units(dim.hierarchy("ymd"))
=======
        elements = time_hierarchy_elements(dim.hierarchy("ymd"))
>>>>>>> Started new 'time' module
        self.assertSequenceEqual(["year", "month", "day"], elements)

    def test_no_roles(self):
        dim = self.workspace.dimension("invalid_date")

        with self.assertRaises(ArgumentError):
<<<<<<< HEAD
            calendar_hierarchy_units(dim.hierarchy("ymd"))
=======
            time_hierarchy_elements(dim.hierarchy("ymd"))
>>>>>>> Started new 'time' module

    def test_time_path(self):
        date = datetime(2012, 12, 24)

<<<<<<< HEAD
        self.assertEqual([], self.cal.path(date, []))
        self.assertEqual([2012], self.cal.path(date, ["year"]))
        self.assertEqual([12, 24], self.cal.path(date, ["month", "day"]))
        self.assertEqual([2012, 4], self.cal.path(date, ["year", "quarter"]))

    def test_path_weekday(self):
        # This is monday:
        date = datetime(2013, 10, 21)
        self.assertEqual([0], self.cal.path(date, ["weekday"]))

        # Week start: Sunday
        self.cal.first_weekday = 6
        self.assertEqual([1], self.cal.path(date, ["weekday"]))

        # Week start: Saturday
        self.cal.first_weekday = 5
        self.assertEqual([2], self.cal.path(date, ["weekday"]))

    def test_truncate(self):
        date = datetime(2012, 1, 10)
        return
        self.assertEqual(datetime(2012, 1, 10), 0, "year")
=======
        self.assertEqual([], time_path(date, []))
        self.assertEqual([2012], time_path(date, ["year"]))
        self.assertEqual([12, 24], time_path(date, ["month", "day"]))
        self.assertEqual([2012, 4], time_path(date, ["year", "quarter"]))

>>>>>>> Started new 'time' module
