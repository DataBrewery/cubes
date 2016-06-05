# -*- encoding: utf-8 -*-
"""Date and time utilities."""

from __future__ import absolute_import

import re

from dateutil.relativedelta import relativedelta
from dateutil.relativedelta import MO, TU, WE, TH, FR, SA, SU
from dateutil.tz import gettz, tzlocal, tzstr
from datetime import datetime
from time import gmtime

from .model import Hierarchy
from .errors import ArgumentError, ConfigurationError
from . import compat

__all__ = (
    "Calendar",
    "calendar_hierarchy_units"
)


_CALENDAR_UNITS = ["year", "quarter", "month", "day", "hour", "minute",
                    "weekday"]


UNIT_YEAR = 8
UNIT_QUARTER = 7
UNIT_MONTH = 6
UNIT_WEEK = 5
UNIT_DAY = 4
UNIT_HOUR = 3
UNIT_MINUTE = 2
UNIT_SECOND = 1


_UNIT_ORDER = {
    "year": UNIT_YEAR,
    "quarter": UNIT_QUARTER,
    "month": UNIT_MONTH,
    "week": UNIT_WEEK,
    "day": UNIT_DAY,
    "hour": UNIT_HOUR,
    "minute": UNIT_MINUTE,
    "second": UNIT_SECOND
}

_DATEUTIL_WEEKDAYS = { 0: MO, 1: TU, 2: WE, 3: TH, 4: FR, 5: SA, 6: SU }

_WEEKDAY_NUMBERS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6
}

RELATIVE_FINE_TIME_RX = re.compile(r"(?P<offset>\d+)?"
                                    "(?P<unit>\w+)"
                                    "(?P<direction>(ago|forward))")


RELATIVE_TRUNCATED_TIME_RX = re.compile(r"(?P<direction>(last|next))"
                                         "(?P<offset>\d+)?"
                                         "(?P<unit>\w+)")

month_to_quarter = lambda month: ((month - 1) // 3) + 1


def calendar_hierarchy_units(hierarchy):
    """Return time units for levels in the hierarchy. The hierarchy is
    expected to be a date/time hierarchy and every level should have a `role`
    property specified. If the role is not specified, then the role is
    determined from the level name.

    Roles/units: `year`, `quarter`, `month`, `day`, `hour`, `minute`,
    `weekday`

    If unknown role is encountered an exception is raised."""

    units = []

    for level in hierarchy.levels:
        role = level.role or level.name

        if role in _CALENDAR_UNITS:
            units.append(role)
        else:
            raise ArgumentError("Unknown time role '%s' for level '%s'"
                                % (role, str(level)))

    return units


def add_time_units(time, unit, amount):
    """Subtract `amount` number of `unit`s from datetime object `time`."""

    args = {}
    if unit == 'hour':
        args['hours'] = amount
    elif unit == 'day':
        args['days'] = amount
    elif unit == 'week':
        args['days'] = amount * 7
    elif unit == 'month':
        args['months'] = amount
    elif unit == 'quarter':
        args['months'] = amount * 3
    elif unit == 'year':
        args['years'] = amount
    else:
        raise ArgumentError("Unknown unit %s for subtraction.")

    return time + relativedelta(**args)


class Calendar(object):
    def __init__(self, first_weekday=0, timezone=None):
        """Creates a Calendar object for providing date/time paths and for
        relative date/time manipulation.

        Values for `first_weekday` are 0 for Monday, 6 for Sunday. Default is
        0."""

        if isinstance(first_weekday, compat.string_type):
            try:
                self.first_weekday = _WEEKDAY_NUMBERS[first_weekday.lower()]
            except KeyError:
                raise ConfigurationError("Unknown weekday name %s" %
                                         first_weekday)
        else:
            value = int(first_weekday)
            if value < 0 or value >= 7:
                raise ConfigurationError("Invalid weekday number %s" %
                                         value)
            self.first_weekday = int(first_weekday)

        if timezone:
            self.timezone_name = timezone
            self.timezone = gettz(timezone) or tzstr(timezone)
        else:
            self.timezone_name = datetime.now(tzlocal()).tzname()
            self.timezone = tzlocal()

    def now(self):
        """Returns current date in the calendar's timezone."""
        return datetime.now(self.timezone)

    def path(self, time, units):
        """Returns a path from `time` containing date/time `units`. `units`
        can be a list of strings or a `Hierarchy` object."""

        if not units:
            return []

        if isinstance(units, Hierarchy):
            units = calendar_hierarchy_units(units)

        path = []

        for unit in units:
            if unit in ("year", "month", "day", "hour", "minute"):
                value = getattr(time, unit)
            elif unit == "quarter":
                value = month_to_quarter(time.month)
            elif unit == "weekday":
                value = (time.weekday() - self.first_weekday) % 7
            else:
                raise ArgumentError("Unknown calendar unit '%s'" % (unit, ))
            path.append(value)

        return path

    def now_path(self, units):
        """Returns a path representing current date and time with `units` as
        path items."""

        return self.path(self.now(), units)

    def truncate_time(self, time, unit):
        """Truncates the `time` to calendar unit `unit`. Consider week start
        day from the calendar."""

        unit_order = _UNIT_ORDER[unit]

        # Seconds are our finest granularity
        time = time.replace(microsecond=0)

        if unit_order > UNIT_MINUTE:
            time = time.replace(minute=0, second=0)
        elif unit_order > UNIT_SECOND:
            time = time.replace(second=0)

        if unit == 'hour':
            pass

        elif unit == 'day':
            time = time.replace(hour=0)

        elif unit == 'week':
            time = time.replace(hour=0)

            weekday = _DATEUTIL_WEEKDAYS[self.first_weekday]
            time = time + relativedelta(days=-6, weekday=weekday)

        elif unit == 'month':
            time = time.replace(day=1, hour=0)

        elif unit == 'quarter':
            month = (month_to_quarter(time.month) - 1) * 3 + 1
            time = time.replace(month=month, day=1, hour=0)

        elif unit == 'year':
            time = time.replace(month=1, day=1, hour=0)

        else:
            raise ValueError("Unrecognized unit: %s" % unit)

        return time

    def since_period_start(self, period, unit, time=None):
        """Returns distance between `time` and the nearest `period` start
        relative to `time` in `unit` units. For example: distance between
        today and start of this year."""

        if not time:
            time = self.now()

        start = self.truncate_time(time, period)
        diff = time - start

        if unit == "day":
            return diff.days
        elif unit == "hour":
            return diff.days * 24 + (diff.seconds // 3600)
        elif unit == "minute":
            return diff.days * 1440 + (diff.seconds // 60)
        elif unit == "second":
            return diff.days * 86400 + diff.seconds
        else:
            raise ValueError("Unrecognized period unit: %s" % unit)

    def named_relative_path(self, reference, units, date=None):
        """"""

        date = date or self.now()

        truncate = False
        relative_match = RELATIVE_FINE_TIME_RX.match(reference)
        if not relative_match:
            truncate = True
            relative_match = RELATIVE_TRUNCATED_TIME_RX.match(reference)

        if reference == "today":
            pass

        elif reference == "yesterday":
            date = date - relativedelta(days=1)

        elif reference == "tomorrow":
            date = date + relativedelta(days=1)

        elif relative_match:
            offset = relative_match.group("offset")
            if offset:
                try:
                    offset = int(offset)
                except ValueError:
                    raise ArgumentError("Relative time offset should be a "
                                        "number")
            else:
                offset = 1

            unit = relative_match.group("unit")
            if unit.endswith("s"):
                unit = unit[:-1]

            direction = relative_match.group("direction")

            if direction in ("ago", "last"):
                offset = -offset

            if truncate:
                date = self.truncate_time(date, unit)

            date = add_time_units(date, unit, offset)

        else:
            # TODO: UNITstart, UNITend
            raise ValueError(reference)

        return self.path(date, units)


class CalendarMemberConverter(object):
    def __init__(self, calendar):
        self.calendar = calendar

    def __call__(self, dimension, hierarchy, path):
        if len(path) != 1:
            return path

        units = hierarchy.level_names
        value = path[0]
        try:
            path = self.calendar.named_relative_path(value, units)
        except ValueError:
            return [value]

        return path

