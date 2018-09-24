# -*- coding: utf-8 -*-

from __future__ import unicode_literals


class QueryBuilder(object):
    def __init__(self, request, browser):
        self.request = request
        self.model = request.model
        self.browser = browser

    def build(self):
        raise NotImplementedError()

    def get_meta_data(self, query):
        return {}
