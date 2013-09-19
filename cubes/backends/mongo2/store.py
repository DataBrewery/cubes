# -*- coding=utf -*-
from ...stores import Store
import pymongo

__all__ = []

class Mongo2Store(Store):
    def __init__(self, url, **options):
        self.client = pymongo.MongoClient(url, read_preference=pymongo.read_preferences.ReadPreference.SECONDARY)

    def model_provider_name(self):
        return 'default'

