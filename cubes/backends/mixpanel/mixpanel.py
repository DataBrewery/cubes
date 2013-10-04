#! /usr/bin/env python
#
# Mixpanel, Inc. -- http://mixpanel.com/
#
# Python API client library to consume mixpanel.com analytics data.

import hashlib
import urllib
import time
try:
    import json
except ImportError:
    import simplejson as json

class MixpanelError(Exception):
    pass

class Mixpanel(object):

    ENDPOINT = 'http://mixpanel.com/api'
    DATA_ENDPOINT = 'http://data.mixpanel.com/api'
    VERSION = '2.0'

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret

    def request(self, methods, params, format='json', is_data=False):
        """
            methods - List of methods to be joined, e.g. ['events', 'properties', 'values']
                      will give us http://mixpanel.com/api/2.0/events/properties/values/
            params - Extra parameters associated with method
        """
        params['api_key'] = self.api_key
        params['expire'] = int(time.time()) + 600   # Grant this request 10 minutes.
        params['format'] = format
        if 'sig' in params: del params['sig']
        params['sig'] = self.hash_args(params)

        endpoint = self.DATA_ENDPOINT if is_data else self.ENDPOINT
        request_url = '/'.join([endpoint, str(self.VERSION)] + methods) + '/?' + self.unicode_urlencode(params)

        response = urllib.urlopen(request_url)

        # Standard response or error response is a JSON. Data response is one
        # JSON per line
        if not is_data or response.getcode() != 200:
            result = json.loads(response.read())
            if "error" in result:
                raise MixpanelError(result["error"])
            else:
                return result
        else:
            return _MixpanelDataIterator(response)

    def unicode_urlencode(self, params):
        """
            Convert lists to JSON encoded strings, and correctly handle any
            unicode URL parameters.
        """
        if isinstance(params, dict):
            params = params.items()
        for i, param in enumerate(params):
            if isinstance(param[1], list):
                params[i] = (param[0], json.dumps(param[1]),)

        return urllib.urlencode(
            [(k, isinstance(v, unicode) and v.encode('utf-8') or v) for k, v in params]
        )

    def hash_args(self, args, secret=None):
        """
            Hashes arguments by joining key=value pairs, appending a secret, and
            then taking the MD5 hex digest.
        """
        for a in args:
            if isinstance(args[a], list): args[a] = json.dumps(args[a])

        args_joined = ''
        for a in sorted(args.keys()):
            if isinstance(a, unicode):
                args_joined += a.encode('utf-8')
            else:
                args_joined += str(a)

            args_joined += '='

            if isinstance(args[a], unicode):
                args_joined += args[a].encode('utf-8')
            else:
                args_joined += str(args[a])

        hash = hashlib.md5(args_joined)

        if secret:
            hash.update(secret)
        elif self.api_secret:
            hash.update(self.api_secret)
        return hash.hexdigest()

class _MixpanelDataIterator(object):
    def __init__(self, data):
        self.line_iterator = iter(data)

    def __iter__(self):
        return self

    def next(self):
        # From Mixpanel Documentation:
        #
        # One event per line, sorted by increasing timestamp. Each line is a
        # JSON dict, but the file itself is not valid JSON because there is no
        # enclosing object. Timestamps are in project time but expressed as
        # Unix time codes (but from_date and to_date are still interpreted in
        # project time).
        #
        # Source: https://mixpanel.com/docs/api-documentation/exporting-raw-data-you-inserted-into-mixpanel
        #
        line = next(self.line_iterator)
        return json.loads(line)

if __name__ == '__main__':
    api = Mixpanel(
        api_key = 'YOUR KEY',
        api_secret = 'YOUR SECRET'
    )
    data = api.request(['events'], {
        'event' : ['pages',],
        'unit' : 'hour',
        'interval' : 24,
        'type': 'general'
    })
    print data
