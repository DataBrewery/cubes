import logging
from cubes.common import get_logger
from cubes.workspace import Workspace
from .browser import MongoBrowser

__all__ = [
    "create_workspace"
]

def create_workspace(model, **options):
    return MongoWorkspace(model, **options)

class MongoWorkspace(Workspace):

    def __init__(self, model, **options):
        super(MongoWorkspace, self).__init__(model, **options)
        self.logger = get_logger()
        self.metadata = {}

    def browser(self, cube, locale=None):
        self.logger.debug('browser: %s %s', cube, locale)

        model = self.localized_model(locale)
        cube = model.cube(cube)

        browser = MongoBrowser(
            cube,
            locale=locale,
            metadata=self.metadata,
            **self.options)

        return browser
