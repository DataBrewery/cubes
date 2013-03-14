import logging
from cubes.mapper import SnowflakeMapper, DenormalizedMapper
from cubes.common import get_logger
from cubes.errors import *
from cubes.browser import *
from cubes.computation import *
from cubes.workspace import Workspace

import pymongo
import bson


__all__ = [
    "create_workspace"
]

def create_workspace(model, **options):
    print 'MODEL:', model
    print 'options:', options

    return MongoWorkspace(model, options)



class MongoWorkspace(Workspace):
    def __init__(self, model, **options):
        super(MongoWorkspace, self).__init__(model)
        self.data_store = data_store
        self.logger = get_logger()

    def browser(self, cube, locale=None):
        print 'browser:', cube, locale

        model = self.localized_model(locale)
        cube = model.cube(cube)

        browser = MongoBrowser(
            cube,
            locale=locale,
            metadata=self.metadata,
            **self.options)

        return browser


class MongoBrowser(AggregationBrowser):
    def __init__(self, cube, locale=None, metadata={}, **options):
        super(MongoBrowser, self).__init__(cube)
        self.data_store = pymongo.MongoClient(**options)
