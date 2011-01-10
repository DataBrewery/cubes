import unittest
import os

tests_path = os.path.dirname(os.path.abspath(__file__))

class BaseCase(object):

    def setup(self):
        pass

    def teardown(self):
        pass
