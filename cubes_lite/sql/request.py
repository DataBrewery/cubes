# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import collections

from cubes_lite.query import Request, Response

__all__ = (
    'RequestType',

    'ListSQLRequest',
    'ListSQLResponse',

    'OneRowSQLRequest',
    'OneRowSQLResponse',
)


class RequestType(object):
    total = 'total'
    data = 'data'


class ListSQLResponse(Response):
    def __init__(self, *args, **kwargs):
        super(ListSQLResponse, self).__init__(*args, **kwargs)
        self.labels = None
        self._batch = None

    def __iter__(self):
        while True:
            if not self._batch:
                many = self._data.fetchmany()
                if not many:
                    break
                self._batch = collections.deque(many)

            row = self._batch.popleft()

            if self.labels:
                yield dict(zip(self.labels, row))
            else:
                yield row


class ListSQLRequest(Request):
    response_cls = ListSQLResponse


class OneRowSQLResponse(ListSQLResponse):
    @property
    def data(self):
        return super(OneRowSQLResponse, self).data()[0]


class OneRowSQLRequest(ListSQLRequest):
    response_cls = OneRowSQLResponse

    def __init__(
        self, model, type_, conditions=None, aggregates=None,
        **options
    ):
        super(OneRowSQLRequest, self).__init__(
            model, type_, conditions, aggregates,
            **options
        )
