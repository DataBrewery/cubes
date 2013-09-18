import re
from functools import partial
import pytz
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta, SA
from utils import now
import logging


_NOOP = lambda x: '||%s||' % x

# FIXME: Warning: this kills all multiple argument occurences
# This function removes all duplicates of query parameters that can be
# obtained through args.getlist() (such as "?drilldown=x&drilldown=y")
def proc_wildcards(args):
    copy = args.copy()
    for k, v in args.iterlists():
        k = op(k)
        v = [ op(ve) for ve in v ]
        copy.setlist(k, v)
    return copy


def op(target):
    matches = re.finditer(r'\|\|([\w\d]+)\|\|', target)
    for mk in matches:
        token = mk.group(1)
        new_val = transform_token(token)
        target = target.replace(mk.group(), new_val)
        logging.debug("Replaced wildcard with %s", target)
    return target


def truncated_now(unit):
    d = now()
    d = d.replace(minute=0, second=0, microsecond=0)
    if unit == 'hour':
        pass
    elif unit == 'day':
        d = d.replace(hour=0)
    elif unit == 'week':
        d = d.replace(hour=0)
        # calc most recent week beginning
        # TODO make week beginning configurable
        #d = d - timedelta(days=( d.weekday() + 2 if d.weekday() < 5 else d.weekday() - 5 ))
        d = d + relativedelta(days=-6, weekday=SA)
    elif unit == 'month':
        d = d.replace(day=1, hour=0)
    elif unit == 'quarter':
        d = d.replace(day=1, hour=0)
        # TODO calc most recent beginning of a quarter
        d = d - relativedelta(months=((d.month - 1) % 3))
    elif unit == 'year':
        d = d.replace(month=1, day=1, hour=0)
    else:
        raise ValueError("Unrecognized unit: %s" % unit)
    return d

def subtract_units(d, amt, unit):
    tdargs = {}
    if unit == 'hour':
        tdargs['hours'] = amt
    elif unit == 'day':
        tdargs['days'] = amt
    elif unit == 'week':
        tdargs['days'] = amt * 7
    elif unit == 'month':
        tdargs['months'] = amt 
    elif unit == 'quarter':
        tdargs['months'] = amt * 3
    elif unit == 'year':
        tdargs['years'] = amt 
    return d - relativedelta(**tdargs)

_the_n_regex = re.compile(r'^last(\d+)(\w+)?$')

_UNITS = set(['hour', 'day', 'week', 'month', 'quarter', 'year'])

def lastN(token, amt=14, unit="day", format='%Y,%m,%d', tzinfo='America/NewYork'):
    m = _the_n_regex.search(token)
    if m:
        munit = m.group(2).lower() if m.group(2) is not None else ''
        if munit in _UNITS:
            unit = munit
        elif munit[:-1] in _UNITS:
            unit = munit[:-1]
        mamt = int(m.group(1))
        if mamt >= 0:
            amt = mamt
    # start with now() truncated to most recent instance of the unit
    n = truncated_now(unit)
    n = subtract_units(n, amt, unit)
    if unit == 'hour':
        format = format + ",%H"
    return n.strftime(format)

def transform_token(token):
    if _wildcards.has_key(token):
        return _wildcards[token](token)
    for func in _regex_wildcards:
        tx = func(token)
        if tx is not None:
            return tx
    return _NOOP

_wildcards = {
    'today': partial(lastN, amt=0, unit='day', format='%Y,%m,%d'),
    'yesterday': partial(lastN, amt=1, unit='day', format='%Y,%m,%d')
}

_regex_wildcards = ( lastN, )

if __name__ == '__main__':
    cuts = (
        'event_date:||last7||-||yesterday||',
        'event_date:||last7weeks||-||today||',
        'event_date:||last0month||-||yesterday||',
        'event_date:||last7month||-||yesterday||',
        'event_date:||last7quarters||-||yesterday||',
        'event_date:||last7years||-||yesterday||',
    )
    for cut in cuts:
        a = { 'cut': cut }
        a2 = proc_wildcards(a)
        print "%-40s  %s" % (cut, a2)
