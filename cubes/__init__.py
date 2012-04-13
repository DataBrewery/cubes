"""OLAP Cubes"""

__version__ = "0.8.1"

from browser import *
from model import *

import util
import backends

import common
from common import logger_name

common._configure_logger()

__all__ = [
    "logger_name",
    "__version__"
]

__all__ += browser.__all__
__all__ += model.__all__