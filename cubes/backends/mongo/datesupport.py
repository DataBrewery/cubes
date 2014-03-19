from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from dateutil.tz import *

from functools import partial
import pytz


DATE_PARTS = ['year', 'month', 'day']
TIME_PARTS = ['hour', 'minute', 'second', 'microsecond']

ALL_NONWEEK_PARTS = ['year', 'month', 'day'] + TIME_PARTS
ALL_WEEK_PARTS = ['week', 'dow_sort'] + TIME_PARTS


def enum(**enums):
    return type('Enum', (), enums)


WEEK_DAY = enum( MONDAY=0, TUESDAY=1, WEDNESDAY=2, THRUSDAY=3, \
                  FRIDAY=4, SATURDAY=5, SUNDAY=6)


WEEK_DAY_NAMES = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')


class MongoDateSupport(object):
    def __init__(self, logger, calendar):
        self.logger = logger
        self.timezone = calendar.timezone_name

        # calnedar.first_weekday is guaranteed to be a number
        self.start_of_week_weekday = calendar.first_weekday

        if (self.start_of_week_weekday == 0):
            self.end_of_week_weekday = WEEK_DAY.SUNDAY
        else:
            self.end_of_week_weekday = (self.start_of_week_weekday - 1)

        self.logger.debug("DateSupport created with timezone %s and start_of_week_weekday %s and end_of_week_weekday %s", self.timezone, self.start_of_week_weekday, self.end_of_week_weekday)

        self.datepart_functions = {
            'year': lambda x:x.year,
            'month': lambda x:x.month,
            'dow': self.calc_dow,
            'dow_sort': self.calc_dow_sort,
            'week': self.calc_week,
            'day': lambda x:x.day,
            'hour': lambda x:x.hour,
            'minute': lambda x:x.minute,
            'second': lambda x:x.second,
            'microsecond': lambda x:x.microsecond,
        }


        self.date_norm_map = {
            'month': 1,
            'day': 1,
            'hour': 0,
            'minute': 0,
            'second': 0,
            'microsecond': 0,
        }


    # filter, given a datepart, determines a datetime object for the current data
    def so_far_filter(self, initial, datepart, key=lambda x:x):
        def _so_far_filter(dt, initial, datepart):
            dateparts = list(ALL_WEEK_PARTS if datepart == 'week' else ALL_NONWEEK_PARTS)

            dt = key(dt)

            def _print(header):
                self.logger.debug("%s %s %s %s %s", header, dp, str(dp_fn(dt)) + ':' + str(dp_fn(initial)),dt.isoformat(), initial.isoformat())

            # for dateparts at greater granularity, if value is > than initial, discard.
            for dp in dateparts[dateparts.index(datepart) + 1:]:
                dp_fn = self.datepart_functions.get(dp)
                if dp_fn(dt) > dp_fn(initial):
                    _print('DISCARDED')
                    return None
                elif dp_fn(dt) < dp_fn(initial):
                    _print('KEPT')
                    return dt
            _print('KEPT')
            return dt
        return partial(_so_far_filter, initial=initial, datepart=datepart)


    def date_as_utc(self, year, tzinfo=None, **kwargs):

        tzinfo = tzinfo or self.timezone

        dateparts = {'year': year}
        dateparts.update(kwargs)

        date = datetime(**dateparts)
        tzinfo.localize(date)

        return date.astimezone(tzutc())


    def get_date_for_week(self, year, week):
        if week < 1:
            raise ValueError('Week must be greater than 0')

        dt = datetime(year, 1, 1)

        while dt.weekday() != self.end_of_week_weekday:
            dt += timedelta(1)

        week -= 1
        dt += timedelta(7 * week)

        return dt

    def calc_week(self, dt):
        return self.get_week_end_date(dt).strftime('%Y-%m-%d')

    def calc_dow(self, dt):
        return WEEK_DAY_NAMES[ dt.weekday() ]

    def calc_dow_sort(self, dt):
        return dt.weekday() + (7 - self.start_of_week_weekday) if dt.weekday() < self.start_of_week_weekday else dt.weekday() - self.start_of_week_weekday

    def clear(self, dt, parts=TIME_PARTS):
        replace_dict = {}

        for p in parts:
            replace_dict[p] = self.date_norm_map.get(p)

        return dt.replace(**replace_dict)


    def get_week_end_date(self, dt):
        dr = self.clear(dt)
        while dr.weekday() != self.end_of_week_weekday:
            dr += timedelta(1)
        return dr

    def get_week_start_date(self, dt):
        dr = self.clear(dt)
        while dr.weekday() != self.start_of_week_weekday:
                dr -= timedelta(1)
        return dr


