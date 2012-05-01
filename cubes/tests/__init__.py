import unittest
import os

import model
import browser
import combinations
import default_sql_backend
import sql_star_browser

from cubes.common import get_logger
import logging

logger = get_logger()
logger.setLevel(logging.DEBUG)

def suite():
    suite = unittest.TestSuite()

    suite.addTest(model.suite())
    suite.addTest(browser.suite())
    suite.addTest(combinations.suite())
    suite.addTest(default_sql_backend.suite())
    suite.addTest(sql_star_browser.suite())

    return suite
