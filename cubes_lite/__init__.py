# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import os


__version__ = '0.1'


PACKAGE_NAME = os.path.basename(os.path.dirname(__file__))

import compat
import errors
import loggers
from .query import *
from .model import *
from .sql import *
