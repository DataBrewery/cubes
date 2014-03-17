# -*- coding=utf -*-
from ...stores import Store
import pymongo

__all__ = []

class MongoStore(Store):
    def __init__(self, url, database=None, collection=None, **options):
        self.client = pymongo.MongoClient(url, read_preference=pymongo.read_preferences.ReadPreference.SECONDARY)
        self.database = database
        self.collection = collection

