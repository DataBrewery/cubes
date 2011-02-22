import unittest
import os
import json
import re

import cubes

from test_model import *
from test_simple_sql import *
from test_aggregations import *
from test_combinations import *
from test_cubes import *

test_cases = [
              ModelValidatorTestCase,
              ModelFromDictionaryTestCase, 
              ModelTestCase,
              AggregationsBasicsTestCase,
              CombinationsTestCase,
              CubeComputationTestCase,
              SQLBuiderTestCase,
              SQLBrowserTestCase
                ]

def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for test_class in test_cases:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    return suite

# 
# 
# if __name__ == '__main__':
#     unittest.main()
