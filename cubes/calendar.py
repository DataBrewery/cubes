# -*- coding=utf -*-
"""Date and time utilities."""

from datetime import datetime, timedelta
from .errors import *
from time import strftime, gmtime

try:
    import pytz
except ImportError:
    from .common import MissingPackage
    pytz = MissingPackage("pytz", "Calendar date and time utilities")


__all__ = (
    "Calendar",
    "calendar_hierarchy_units"
)


_calendar_units = ["year", "quarter", "month", "day", "hour", "minute",
                    "weekday"]


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

        if role in _calendar_units:
            units.append(role)
        else:
            raise ArgumentError("Unknown time role '%s' for level '%s'"
                                % (role, str(level)))

    return units


def local_timezone_name():
    """Return system's local timezone"""
    return strftime("%Z", gmtime())

_utc = pytz.timezone('UTC')

_relative_regexp = re.compile(r"(?P<direction>before|next)"
                               "(?P<offset>\d+)?"
                               "(?P<unit>\w+)")

class Calendar(object):
    def __init__(self, first_weekday=0, timezone=None):
        """Creates a Calendar object for providing date/time paths and for
        relative date/time manipulation.

        Values for `first_weekday` are 0 for Monday, 6 for Sunday. Default is
        0."""

        self.first_weekday = first_weekday

        if timezone:
            self.timezone_name = timezone
        else:
            self.timezone_name = local_timezone_name()
        self.timezone = pytz.timezone(self.timezone_name)

    def now(self):
        """Returns current date in the calendar's timezone."""
        current_moment = _utc.localize(datetime.utcnow())
        return current_moment.astimezone(self.timezone)

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
                value = ((time.month - 1) / 3) + 1
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

    def offset_path(self, name, date):
        """"""

        date = date or self.now()
        if name == "today":
            pass
        elif name == "yesterday":
            date = date - relativedelta(days=1)
        elif name == "tomorrow":
            date = date + relativedelta(days=1)

        # TODO: units?
        retunr self.path(date)

        # today
        # tomorrow
        # yesterday
        # UNITstart
        # UNITend
        # COUNTUNITSago: 10weeksago
        # 
