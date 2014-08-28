# -*- coding=utf -*-

from __future__ import absolute_import

import datetime
import calendar

from ... import compat

__all__ = [
    "coalesce_date_path",
    "time_to_path",
    "timestamp_to_record"
]

def _week_value(dt, as_string=False):
    """
    Mixpanel weeks start on Monday. Given a datetime object or a date string of format YYYY-MM-DD,
    returns a YYYY-MM-DD string for the Monday of that week.
    """
    dt = datetime.datetime.strptime(dt, '%Y-%m-%d') if isinstance(dt, compat.string_type) else dt
    dt = ( dt - datetime.timedelta(days=dt.weekday()) )
    return ( dt.strftime("%Y-%m-%d") if as_string else dt )

_week_path_readers = ( lambda v: datetime.datetime.strptime(v, '%Y-%m-%d'), lambda v: datetime.datetime.strptime(v, '%Y-%m-%d'), int )

_lower_date = datetime.datetime(2008, 1, 1)

def coalesce_date_path(path, bound, hier='ymdh'):
    if str(hier) == 'wdh':
        return _coalesce_date_wdh(path, bound)
    else:
        return _coalesce_date_ymdh(path, bound)

def _coalesce_date_wdh(path, bound):
    path = [ _week_path_readers[i](path[i]) for i, v in enumerate(list(path or [])) ]
    effective_dt = path[1] if len(path) > 1 else ( path[0] if len(path) else ( _lower_date if bound == 0 else datetime.datetime.today() ) )

    if bound == 0:
        # at week level, first monday
        if len(path) < 1:
            return _week_value(effective_dt)
        else:
            return effective_dt.replace(hour=0)
    else:
        # end of this week, sunday
        result = ( _week_value(effective_dt) + datetime.timedelta(days=6) ) if len(path) < 2 else effective_dt
        return min(result, datetime.datetime.today())


def _coalesce_date_ymdh(path, bound):
    # Bound: 0: lower, 1:upper

    # Convert path elements
    path = [ int(v) for v in list(path or []) ]

    length = len(path)

    # Lower bound:
    if bound == 0:
        lower = [_lower_date.year, _lower_date.month, _lower_date.day]
        result = path + lower[len(path):]
        return datetime.datetime(**(dict(zip(['year', 'month', 'day'], result))))

    # Upper bound requires special handling
    today = datetime.datetime.today()

    delta = datetime.timedelta(1)
    # Make path of length 4
    (year, month, day, hour) = tuple(path + [None]*(4-len(path)))

    # hours are ignored - Mixpanel does not allow to use hours for cuts

    if not year:
        return today

    elif year and month and day:
        date = datetime.date(year, month, day)

    elif year < today.year:
        date = datetime.date(year+1, 1, 1) - delta

    elif year == today.year and month and month < today.month:
        day = calendar.monthrange(year, month)[1]
        date = datetime.date(year, month, day)

    elif year == today.year and month == today.month and not day:
        date = datetime.date(year, month, today.day)

    elif year > today.year:
        month = month or 1
        day = calendar.monthrange(year, month)[1]
        date = datetime.date(year, month, day)

    else:
        date = today

    return date

def timestamp_to_record(timestamp):
    """Returns a path from `timestamp` in the ``ymdh`` hierarchy."""
    time = datetime.datetime.fromtimestamp(timestamp)
    record = {
        "time.year": time.year,
        "time.month": time.month,
        "time.day": time.day,
        "time.hour": time.hour
    }
    return record

def time_to_path(time_string, last_level, hier='ymdh'):
    """Converts `time_string` into a time path. `time_string` can have format:
        ``yyyy-mm-dd`` or ``yyyy-mm-dd hh:mm:ss``. Only hour is considered
        from the time."""

    split = time_string.split(" ")
    if len(split) > 1:
        date, time = split
    else:
        date = split[0]
        time = None

    if hier == 'wdh':
        if last_level == 'week':
            time_path = [ _week_value(date, True) ]
        else:
            time_path = [ _week_value(date, True), date ]
    else:
        time_path = [int(v) for v in date.split("-")]
    # Only hour is assumed
    if time:
        hour = time.split(":")[0]
        time_path.append(int(hour))

    return tuple(time_path)
