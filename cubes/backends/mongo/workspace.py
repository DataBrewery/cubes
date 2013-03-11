# -*- coding=utf -*-

from cubes.workspace import Workspace
from cubes.common import get_logger
from browser import *
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

    mongo = pymongo.MongoClient(**options)

    workspace = MongoWorkspace(model, mongo, **options)

    return workspace

class MongoWorkspace(Workspace):

    """Factory for browsers"""
    def __init__(self, model, mongo, **options):
        """Create a workspace. For description of options see
        `create_workspace()` """

        super(MongoWorkspace, self).__init__(model)

        self.logger = get_logger()

        self.mongo = mongo
        self.schema = options.get("schema")
        self.options = options

    def browser(self, cube, locale=None):
        """Returns a browser for a `cube`."""
        model = self.localized_model(locale)
        cube = model.cube(cube)
        browser = MongoSimpleCubeBrowser(cube, self.mongo.SquarespaceEvents.shopper_events)
        return browser