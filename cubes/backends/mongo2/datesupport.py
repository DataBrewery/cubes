from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
import pytz


tz = pytz.timezone('America/New_York')
tz_utc = pytz.timezone('UTC')

DATE_PARTS = ['year', 'month', 'day']
TIME_PARTS = ['hour', 'minute', 'second', 'microsecond']


def enum(**enums):
    return type('Enum', (), enums)


WEEK_DAY = enum( MONDAY=0, TUESDAY=1, WEDNESDAY=2, THRUSDAY=3, \
                  FRIDAY=4, SATURDAY=5, SUNDAY=6)
   

def eastern_date_as_utc(year, **kwargs):

    dateparts = {'year': year, 'tzinfo': tz}
    dateparts.update(kwargs)

    date = datetime(**dateparts)

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
    
    dt = get_next_weekdate(dt, direction='down')
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
}


date_norm_map = {
    'month': 1,
    'day': 1,
    'hour': 0,
    'minute': 0,
    'second': 0,
    'microsecond': 0,
}