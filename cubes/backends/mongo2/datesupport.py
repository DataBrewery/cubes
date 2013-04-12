from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from functools import partial
import pytz


tz = pytz.timezone('America/New_York')
tz_eastern = pytz.timezone('America/New_York')
tz_utc = pytz.timezone('UTC')

DATE_PARTS = ['year', 'month', 'day']
TIME_PARTS = ['hour', 'minute', 'second', 'microsecond']

ALL_PARTS = ['year', 'week', 'month', 'day'] + TIME_PARTS


def enum(**enums):
    return type('Enum', (), enums)


WEEK_DAY = enum( MONDAY=0, TUESDAY=1, WEDNESDAY=2, THRUSDAY=3, \
                  FRIDAY=4, SATURDAY=5, SUNDAY=6)


def so_far_filter(initial, datepart, key=lambda x:x):
    def _so_far_filter(dt, initial, datepart):
        dateparts = list(ALL_PARTS)
        if datepart == 'week':
            dateparts.pop(dateparts.index('month'))
            dateparts.pop(dateparts.index('day'))
        else:
            dateparts.pop(dateparts.index('week'))

        dt = key(dt)

        def _print(header):
            print header, dp, str(dp_fn(dt)) + ':' + str(dp_fn(initial)),dt.isoformat(), initial.isoformat() 

        for dp in dateparts[dateparts.index(datepart) + 1:]:
            dp_fn = datepart_functions.get(dp)
            if dp_fn(dt) > dp_fn(initial):
                # _print('DISCARED')
                return None
            elif dp_fn(dt) < dp_fn(initial):
                # _print('KEPT')
                return dt
        # _print('KEPT')
        return dt
    return partial(_so_far_filter, initial=initial, datepart=datepart)


def date_as_utc(year, tzinfo=tz_eastern, **kwargs):

    dateparts = {'year': year}
    dateparts.update(kwargs)

    date = datetime(**dateparts)
    tzinfo.localize(date)

    return date.astimezone(tz_utc)


def get_date_for_week(year, week):
    if week < 1:
        raise ValueError('Week must be greater than 0')

    dt = datetime(**{
            'year': year,
            'month': 1,
            'day': 1
        })

    while dt.weekday() != WEEK_DAY.FRIDAY:
        dt += timedelta(1)

    week -= 1
    dt += timedelta(7 * week)

    return dt


def calc_week(dt):
    dt = get_next_weekdate(dt, direction='up')
    year = dt.year

    count = 0
    while dt.year == year:
        count += 1
        dt -= timedelta(days=7)

    return (year, count) # the week year might be different


def clear(dt, parts=TIME_PARTS):
    replace_dict = {}

    for p in parts:
        replace_dict[p] = date_norm_map.get(p)

    return dt.replace(**replace_dict)


def get_next_weekdate(dt, direction='up'):
    dr = clear(dt)
    while dr.weekday() != WEEK_DAY.FRIDAY:
        if direction in set(['up', 'asc', '1', 1]):
            dr += timedelta(1)
        else:
            dr -= timedelta(1)

    return dr


datepart_functions = {
    'year': lambda x:x.year,
    'month': lambda x:x.month,
    'week': calc_week,
    'day': lambda x:x.day,
    'hour': lambda x:x.hour,
    'minute': lambda x:x.minute,
    'second': lambda x:x.second,
    'microsecond': lambda x:x.microsecond,
}


date_norm_map = {
    'month': 1,
    'day': 1,
    'hour': 0,
    'minute': 0,
    'second': 0,
    'microsecond': 0,
}