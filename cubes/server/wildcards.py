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
        transform = _wildcards.get(token, _NOOP)
        new_val = transform(token)
        target = target.replace(mk.group(), new_val)
        logging.debug("Replaced wildcard with %s", target)
    return target


def lastN(token, days=14, format='%Y-%m-%d', tzinfo='America/NewYork'):
    n = now()
    n = n - timedelta(days=days)
    return n.strftime(format)


_wildcards = {
    'today': partial(lastN, days=0, format='%Y,%m,%d'),
    'yesterday': partial(lastN, days=1, format='%Y,%m,%d'),
    'last7': partial(lastN, days=7, format='%Y,%m,%d'),
    'last14': partial(lastN, days=14, format='%Y,%m,%d'),
    'last30': partial(lastN, days=30, format='%Y,%m,%d'),
    'last10': partial(lastN, days=10, format='%Y,%m,%d'),
}
