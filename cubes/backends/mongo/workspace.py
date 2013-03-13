# -*- coding=utf -*-

from cubes.workspace import Workspace
from cubes.common import get_logger
from browser import *
from builder import *
import pymongo

__all__ = [
    "create_workspace"
]

def create_workspace(model, **options):
    """Create workspace for `model` with configuration in dictionary
    `options`. This method is used by the slicer server.

    The options are:

    Required:

    * `url` - mongo URL in form of:
      ``?``

    Optional:

    """


    workspace = MongoWorkspace(model, **options)

    return workspace

class MongoWorkspace(Workspace):

    """Factory for browsers"""
    def __init__(self, model, **options):
        """Create a workspace. For description of options see
        `create_workspace()` """

        super(MongoWorkspace, self).__init__(model)

        self.logger = get_logger()

        self.mongo = pymongo.MongoClient(**options)

        self.schema = options.get("schema")
        self.options = options

    def browser(self, cube, locale=None):
        """Returns a browser for a `cube`."""
        model = self.localized_model(locale)
        cube = model.cube(cube)

        db, coll = cube.name.split('.')

        print 'CONNECT', db, coll

        database = self.mongo[db]

        browser = MongoSimpleCubeBrowser(cube, coll, database)
        return browser

    def builder(self, cube):

        db, coll = cube.name.split('.')

        database = self.mongo[db]

        builder = MongoSimpleCubeBuilder(cube, database, coll, cube_collection=coll, required_dimensions = ['t',])
        return builder

