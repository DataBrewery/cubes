"""
:synopsis: Tools for online analytical processing

"""
from base import *

from cubes.backends.mongo.browser import *

__all__ = [
    "MongoSimpleCubeBrowser"
]
