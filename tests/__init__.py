from __future__ import absolute_import

import unittest
import os

from cubes.compat import py3k
if not py3k:
    unittest.TestCase.assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

from . import sql

# from .model import *
# from .browser import *
# from .combinations import *
# from .default_sql_backend import *
# from .sql_star_browser import *


# from cubes.common import get_logger
# import logging
#
# logger = get_logger()
# logger.setLevel(logging.DEBUG)

# def suite():
#     suite = unittest.TestSuite()
#
#     suite.addTest(model.suite())
#     suite.addTest(browser.suite())
#     suite.addTest(combinations.suite())
#     suite.addTest(default_sql_backend.suite())
#     suite.addTest(sql_star_browser.suite())
#
#     return suite
