# -*- encoding: utf-8 -*-
"""Date and time utilities."""

import re

from typing import Dict, List, Optional, Union

from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU
from dateutil.tz import gettz, tzlocal, tzstr
from datetime import datetime, tzinfo

from .metadata import Hierarchy, HierarchyPath, Dimension
from .errors import ArgumentError, ConfigurationError

__all__ = ("Calendar", "calendar_hierarchy_units")


_CALENDAR_UNITS = ["year", "quarter", "month", "day", "hour", "minute", "weekday"]


# FIXME: [typing] Change to enum
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
    "second": UNIT_SECOND,
}

_DATEUTIL_WEEKDAYS = {0: MO, 1: TU, 2: WE, 3: TH, 4: FR, 5: SA, 6: SU}

_WEEKDAY_NUMBERS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

RELATIVE_FINE_TIME_RX = re.compile(
    r"(?P<offset>\d+)?" r"(?P<unit>\w+)(?P<direction>(ago|forward))"
)


RELATIVE_TRUNCATED_TIME_RX = re.compile(
    r"(?P<direction>(last|next))" r"(?P<offset>\d+)?" r"(?P<unit>\w+)"
)

month_to_quarter = lambda month: ((month - 1) // 3) + 1


def calendar_hierarchy_units(hierarchy: Hierarchy) -> List[str]:
    """Return time units for levels in the hierarchy. The hierarchy is
    expected to be a date/time hierarchy and every level should have a `role`
    property specified. If the role is not specified, then the role is
    determined from the level name.

    Roles/units: `year`, `quarter`, `month`, `day`, `hour`, `minute`,
    `weekday`

    If unknown role is encountered an exception is raised."""

    units: List[str]
    units = []

    for level in hierarchy.levels:
        role = level.role or level.name

        if role in _CALENDAR_UNITS:
            units.append(role)
        else:
            raise ArgumentError(
                "Unknown time role '{}' for level '{}'".format(role, str(level))
            )

    return units


def add_time_units(time: datetime, unit: str, amount: int) -> datetime:
    """Subtract `amount` number of `unit`s from datetime object `time`."""

    hours: int = 0
    days: int = 0
    months: int = 0
    years: int = 0

    if unit == "hour":
        hours = amount
    elif unit == "day":
        days = amount
    elif unit == "week":
        days = amount * 7
    elif unit == "month":
        months = amount
    elif unit == "quarter":
        months = amount * 3
    elif unit == "year":
        years = amount
    else:
        raise ArgumentError(f"Unknown unit {unit} for subtraction.")

    return time + relativedelta(hours=hours, days=days, months=months, years=years)


class Calendar:
    timezone_name: Optional[str]
    timezone: tzinfo

    def __init__(
        self, first_weekday: Union[str, int] = 0, timezone: str = None
    ) -> None:
        """Creates a Calendar object for providing date/time paths and for
        relative date/time manipulation.

        Values for `first_weekday` are 0 for Monday, 6 for Sunday. Default is
        0."""

        if isinstance(first_weekday, str):
            try:
                self.first_weekday = _WEEKDAY_NUMBERS[first_weekday.lower()]
            except KeyError:
                raise ConfigurationError(f"Unknown weekday name {first_weekday}")
        else:
            value = int(first_weekday)
            if value < 0 or value >= 7:
                raise ConfigurationError(f"Invalid weekday number {value}")
            self.first_weekday = int(first_weekday)

        if timezone is not None:
            self.timezone_name = timezone
            self.timezone = gettz(timezone) or tzstr(timezone)
        else:
            self.timezone_name = datetime.now(tzlocal()).tzname()
            self.timezone = tzlocal()

    def now(self) -> datetime:
        """Returns current date in the calendar's timezone."""
        return datetime.now(self.timezone)

    def path(self, time: datetime, units: List[str]) -> HierarchyPath:
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
                raise ArgumentError(f"Unknown calendar unit '{unit}'")
            path.append(value)

        return path

    def now_path(self, units: List[str]) -> HierarchyPath:
        """Returns a path representing current date and time with `units` as
        path items."""

        return self.path(self.now(), units)

    def truncate_time(self, time: datetime, unit: str) -> datetime:
        """Truncates the `time` to calendar unit `unit`. Consider week start
        day from the calendar."""

        unit_order = _UNIT_ORDER[unit]

        # Seconds are our finest granularity
        time = time.replace(microsecond=0)

        if unit_order > UNIT_MINUTE:
            time = time.replace(minute=0, second=0)
        elif unit_order > UNIT_SECOND:
            time = time.replace(second=0)

        if unit == "hour":
            pass

        elif unit == "day":
            time = time.replace(hour=0)

        elif unit == "week":
            time = time.replace(hour=0)

            weekday = _DATEUTIL_WEEKDAYS[self.first_weekday]
            time = time + relativedelta(days=-6, weekday=weekday)

        elif unit == "month":
            time = time.replace(day=1, hour=0)

        elif unit == "quarter":
            month = (month_to_quarter(time.month) - 1) * 3 + 1
            time = time.replace(month=month, day=1, hour=0)

        elif unit == "year":
            time = time.replace(month=1, day=1, hour=0)

        else:
            raise ValueError("Unrecognized unit: %s" % unit)

        return time

    def since_period_start(self, period: str, unit: str, time: datetime = None) -> int:
        """Returns distance between `time` and the nearest `period` start
        relative to `time` in `unit` units. For example: distance between
        today and start of this year."""

        if time is None:
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

    def named_relative_path(
        self, reference: str, units: List[str], date: datetime = None
    ) -> HierarchyPath:
        """"""

        offset: int
        date = date or self.now()

        truncate: bool
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
            offset_str = relative_match.group("offset")
            if offset_str is not None:
                try:
                    offset = int(offset_str)
                except ValueError:
                    raise ArgumentError("Relative time offset should be a number")
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


class CalendarMemberConverter:
    calendar: Calendar

    def __init__(self, calendar: Calendar) -> None:
        self.calendar = calendar

    def __call__(
        self, dimension: Dimension, hierarchy: Hierarchy, path: HierarchyPath
    ) -> HierarchyPath:

        if len(path) != 1:
            return path

        units = hierarchy.level_names
        value = path[0]
        try:
            path = self.calendar.named_relative_path(value, units)
        except ValueError:
            return [value]

        return path
