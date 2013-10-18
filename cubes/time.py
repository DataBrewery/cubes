# -*- coding=utf -*-
"""Date and time utilities."""

from datetime import datetime, timedelta
from .errors import *

__all__ = (
        "time_path",
        "time_hierarchy_elements"
        )


_time_elements = ["year", "quarter", "month", "day", "hour", "minute"]


def time_path(time, elements):
    """Returns a path from `date`. `elements` is a list of date elements:
       `year`, `quarter`, `month`, `day`, `hour`, `minute`."""

    if not elements:
        return []

    path = []

    for element in elements:
        if element in ("year", "month", "day", "hour", "minute", "weekday",
                       "isoweekday"):
            value = getattr(time, element)
        elif element == "quarter":
            value = ((time.month - 1) / 3) + 1
        else:
            raise ArgumentError("Unknown date element '%s'" % (element, ))
        path.append(value)

    return path


def time_hierarchy_elements(hierarchy):
    """Return time elements for levels in the hierarchy. The hierarchy is
    expected to be a date/time hierarchy and every level should have a `role`
    property specified. If the role is not specified, then the role is
    determined from the level name.

    Roles/elements: `year`, `quarter`, `month`, `day`, `hour`, `minute`

    If unknown role is encountered an exception is raised."""

    elements = []

    for level in hierarchy.levels:
        role = level.role or level.name

        if role in _time_elements:
            elements.append(role)
        else:
            raise ArgumentError("Unknown time role '%s' for level '%s'"
                                % (role, str(level)))

    return elements
