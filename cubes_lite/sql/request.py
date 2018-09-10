# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import collections

from ..query import Request, Response

__all__ = (
    'RequestType',

    'SQLRequest',
    'SQLResponse',

    'TotalSQLRequest',
    'TotalSQLResponse',
)


class RequestType(object):
    total = 'total'
    data = 'data'


class SQLRequest(Request):
    response_cls = SQLResponse


class SQLResponse(Response):
    def __init__(self, *args, **kwargs):
        super(SQLResponse, self).__init__(*args, **kwargs)
        self.labels = None
        self._batch = None

    def __iter__(self):
        while True:
            if not self._batch:
                many = self.data.fetchmany()
                if not many:
                    break
                self._batch = collections.deque(many)

            row = self._batch.popleft()

            if self.labels:
                yield dict(zip(self.labels, row))
            else:
                yield row


class TotalSQLRequest(SQLRequest):
    response_cls = TotalSQLResponse

    def __init__(
        self, model, type_, conditions=None, aggregates=None,
        **options
    ):
        super(TotalSQLRequest, self).__init__(
            model, type_, conditions, aggregates,
            **options
        )


class TotalSQLResponse(SQLResponse):
    @property
    def data(self):
        return super(TotalSQLResponse, self).data()[0]
