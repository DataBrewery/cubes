# -*-coding=utf -*-

from ...browser import AggregationBrowser

class GoogleAnalyticsBrowser(AggregationBrowser):
    __identifier__ = "ga"

    def __init__(self, cube, store, locale=None, **options):

        self.store = store
        self.cube = cube
        self.locale = locale

    def featuers(self):
        return {
            "actions": []
        }
