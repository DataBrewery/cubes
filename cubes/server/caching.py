# -*- coding: utf-8 -*-
import json
import logging
from functools import update_wrapper, wraps
from datetime import datetime, timedelta
from exceptions import BaseException
import cPickle as pickle
import types

from werkzeug.routing import Rule
from werkzeug.wrappers import Response


def _make_key_str(name, *args, **kwargs):
    key_str = name

    if args:
        key_str += '::' + '::'.join([str(a) for a in args])
    if kwargs:
        key_str += '::' + '::'.join(['%s=%s' % (str(k), str(v)) for k, v in sorted(kwargs.items(), key=lambda x: x[0])])

    return key_str


_NOOP = lambda x: x


def query_ttl_strategy(data):
    import chat2query
    import measures

    if 'q' in data:
        query = chat2query.parse(data['q'])
        config = measures.get_measure_manifest().get(query.measure, {})
        ttl = config.get('ttl', None)
        if ttl:
            logging.getLogger().debug('Using configured ttl: %s', ttl)
        return ttl

    return None


def _default_strategy(data):
    return None


def response_dumps(response):
    return {
        'data': response.data,
        'mimetype': response.content_type
    }


def response_loads(data):
    return Response(data['data'], mimetype=data['mimetype'])



def cacheable(fn):
    @wraps(fn)
    def _cache(self, *args, **kwargs):

        if not hasattr(self, 'cache'):
            logging.getLogger().warn('Object is not configured with cache for @cacheable function: %s', self)
            return fn(self, *args, **kwargs)

        additional_args = getattr(self, 'args', {})

        cache_impl = self.cache

        name = '%s.%s' % (self.__class__.__name__, fn.__name__)
        key = _make_key_str(name, *args, **dict(additional_args.items() + kwargs.items()))

        try:
            v = cache_impl.get(key)

            if not v:
                self.logger.debug('CACHE MISS')
                v = fn(self, *args, **kwargs)
                cache_impl.set(key, v)
            else:
                self.logger.debug('CACHE HIT')
            return v
        except Exception as e:
            self.logger.warn('ERROR, skipping cache')
            self.logger.exception(e)
            v = fn(self, *args, **kwargs)
            try:
                cache_impl.set(key, v)
            finally:
                return v

    return update_wrapper(_cache, fn)



class Cache(object):
    def __setitem__(self, key, value):
        return self.set(key, value)

    def __getitem__(self, key):
        return self.get(key)

    def __delitem__(self, key):
        return self.rem(key)


def trap(fn):
    def _trap(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BaseException as e:
            logging.getLogger().error('%s: %s, %s', fn.__name__, args, kwargs)
            logging.getLogger().exception(e)
    return _trap


class MongoCache(Cache):

    def __init__(self, name, ds, ttl=60, ttl_strategy=_default_strategy, dumps=_NOOP, loads=_NOOP, logger=logging.getLogger(), **kwargs):
        self.ttl = ttl
        self.store = ds.Caches[name]
        self.dumps = dumps
        self.loads = loads
        self.ttl_strategy = ttl_strategy
        self.logger=logger

    @trap
    def set(self, key, val, ttl=None):
        t = ttl or self.ttl_strategy(val) or self.ttl
        n = datetime.utcnow() + timedelta(seconds=t)

        p = {
            '_id': key,
            't': n,
            'd': self.dumps(val)
        }

        self.logger.debug('Set: %s, ttl: %s', key, t)
        item = self.store.save(p)

        return item is not None

    @trap
    def get(self, key):
        n = datetime.utcnow()
        item = self.store.find_one({'_id':key})

        if item:

            item['d'] = self.loads(item['d'])
            exp = item['t']
            if exp >= n:
                self.logger.debug('Hit: %s', key)
                return item['d']
            else:
                self.logger.debug('Stale: %s', key)
                self.store.remove({'_id': key})
                return None
        else:
            self.logger.debug('Miss: %s', key)
            return None

    def rem(self, key):
        n = datetime.utcnow()
        item = self.store.find_one({'_id':key})

        if item:
            self.logger.debug('Remove: %s', key)
            self.store.remove(item)
            return True
        else:
            self.logger.debug('Miss: %s', key)
            return False
