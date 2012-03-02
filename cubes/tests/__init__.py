import unittest
import os

import model
import aggregations
import combinations
import default_sql_backend
import sql_star_browser

def suite():
    suite = unittest.TestSuite()

    suite.addTest(model.suite())
    suite.addTest(aggregations.suite())
    suite.addTest(combinations.suite())
    suite.addTest(default_sql_backend.suite())
    suite.addTest(sql_star_browser.suite())

    return suite
