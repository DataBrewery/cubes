import re
from functools import partial
import pytz
from datetime import datetime, timedelta
from utils import now
import logging


_NOOP = lambda x: '||%s||' % x


def proc_wildcards(args):
    copy = args.copy()
    for k, v in args.items():
        k = op(k)
        v = op(v)
        copy[k] = v
    return copy


def op(target):
    matches = re.finditer(r'\|\|([\w\d]+)\|\|', target)
    for mk in matches:
        token = mk.groups()[0]
        new_val = transform_token(token)
        target = target.replace(mk.group(), new_val)
        logging.debug("Replaced wildcard with %s", target)
    return target


_the_n_regex = re.compile(r'^last(\d+)$')

def lastN(token, days=14, format='%Y-%m-%d', tzinfo='America/NewYork'):
    m = _the_n_regex.search(token)
    if m:
        mdays = int(m.group(1))
        if days > 0:
            days = mdays
    n = now()
    n = n - timedelta(days=days)
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
    'today': partial(lastN, days=0, format='%Y,%m,%d'),
    'yesterday': partial(lastN, days=1, format='%Y,%m,%d'),
    'last7': partial(lastN, days=7, format='%Y,%m,%d'),
    'last14': partial(lastN, days=14, format='%Y,%m,%d'),
    'last30': partial(lastN, days=30, format='%Y,%m,%d'),
    'last10': partial(lastN, days=10, format='%Y,%m,%d'),
}

_regex_wildcards = ( lastN, )

if __name__ == '__main__':
    a = { 'cut': 'event_date:||last7||-||yesterday||' }
    a2 = proc_wildcards(a)
    print a2
