# -*- coding=utf -*-
from .common import CubesTestCaseBase, create_provider
from cubes.errors import *
from cubes.calendar import *
from datetime import datetime


class DateTimeTestCase(CubesTestCaseBase):
    def setUp(self):
        super(DateTimeTestCase,self).setUp()

        self.provider = create_provider("datetime.json")
        self.cal = Calendar()

    def test_empty(self):
        dim = self.provider.dimension("default_date")

        self.assertEqual("date", dim.role)
        self.assertIsNone(dim.level("year").role)

    def test_implicit_roles(self):
        dim = self.provider.dimension("default_date")

        elements = calendar_hierarchy_units(dim.hierarchy("ymd"))
        self.assertSequenceEqual(["year", "month", "day"], elements)

    def test_explicit_roles(self):
        dim = self.provider.dimension("explicit_date")

        elements = calendar_hierarchy_units(dim.hierarchy("ymd"))
        self.assertSequenceEqual(["year", "month", "day"], elements)

    def test_no_roles(self):
        dim = self.provider.dimension("invalid_date")

        with self.assertRaises(ArgumentError):
            calendar_hierarchy_units(dim.hierarchy("ymd"))

    def test_time_path(self):
        date = datetime(2012, 12, 24)

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

    # Reference for the named relative test
    #                              2012
    # 
    #     Január            Február           Marec             Apríl
    # po     2  9 16 23 30     6 13 20 27        5*12 19 26        2  9 16 23 30
    # ut     3 10 17 24 31     7 14 21 28        6 13 20 27        3 10 17 24
    # st     4 11 18 25     1  8 15 22 29        7 14 21 28        4 11 18 25
    # št     5 12 19 26     2  9 16 23       *1  8 15 22 29        5 12 19 26
    # pi     6 13 20 27     3 10 17 24        2  9 16 23 30        6 13 20 27
    # so     7 14 21 28     4 11 18 25        3 10 17 24 31        7 14 21 28
    # ne  1  8 15 22 29     5 12 19 26        4 11 18 25        1  8 15 22 29

    def test_named_relative(self):
        date = datetime(2012, 3, 1)

        units = ["year", "month", "day"]
        path = self.cal.named_relative_path("tomorrow", units, date)
        self.assertEqual([2012, 3, 2], path)

        path = self.cal.named_relative_path("yesterday", units, date)
        self.assertEqual([2012, 2, 29], path)

        path = self.cal.named_relative_path("weekago", units, date)
        self.assertEqual([2012, 2, 23], path)

        path = self.cal.named_relative_path("3weeksago", units, date)
        self.assertEqual([2012, 2, 9], path)

        date = datetime(2012, 3, 12)

        path = self.cal.named_relative_path("monthago", units, date)
        self.assertEqual([2012, 2, 12], path)

        path = self.cal.named_relative_path("12monthsago", units, date)
        self.assertEqual([2011, 3, 12], path)

        path = self.cal.named_relative_path("monthforward", units, date)
        self.assertEqual([2012, 4, 12], path)

        path = self.cal.named_relative_path("12monthsforward", units, date)
        self.assertEqual([2013, 3, 12], path)

    def test_named_relative_truncated(self):
        date = datetime(2012, 3, 1, 10, 30)

        units = ["year", "month", "day", "hour"]

        path = self.cal.named_relative_path("lastweek", units, date)
        self.assertEqual([2012, 2, 20, 0], path)

        path = self.cal.named_relative_path("last3weeks", units, date)
        self.assertEqual([2012, 2, 6, 0], path)

        date = datetime(2012, 3, 12)

        path = self.cal.named_relative_path("lastmonth", units, date)
        self.assertEqual([2012, 2, 1, 0], path)

        path = self.cal.named_relative_path("last12months", units, date)
        self.assertEqual([2011, 3, 1, 0], path)

        path = self.cal.named_relative_path("nextmonth", units, date)
        self.assertEqual([2012, 4, 1, 0], path)

        path = self.cal.named_relative_path("next12months", units, date)
        self.assertEqual([2013, 3, 1,0 ], path)

        path = self.cal.named_relative_path("lastquarter", units, date)
        self.assertEqual([2011,10, 1, 0], path)

        path = self.cal.named_relative_path("lastyear", units, date)
        self.assertEqual([2011, 1, 1,0 ], path)

    def test_distance(self):
        # Meniny (SK): Anna/Hana
        time = datetime(2012, 7, 26, 12, 5)

        self.assertEqual(207, self.cal.since_period_start("year", "day", time))
        self.assertEqual(25, self.cal.since_period_start("quarter", "day", time))
        self.assertEqual(25, self.cal.since_period_start("month", "day", time))
        self.assertEqual(612, self.cal.since_period_start("month", "hour", time))
        self.assertEqual(12, self.cal.since_period_start("day", "hour", time))

        time = datetime(2012, 1, 1, 1, 1)

        self.assertEqual(0, self.cal.since_period_start("year", "day", time))
        self.assertEqual(0, self.cal.since_period_start("quarter", "day", time))
        self.assertEqual(0, self.cal.since_period_start("month", "day", time))
        self.assertEqual(1, self.cal.since_period_start("month", "hour", time))
        self.assertEqual(1, self.cal.since_period_start("day", "hour", time))
