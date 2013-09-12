import os
import unittest

TESTS_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(TESTS_PATH, 'data')

class CubesTestCaseBase(unittest.TestCase):
    def setUp(self):
        self._models_path = os.path.join(TESTS_PATH, 'models')
        self._data_path = os.path.join(TESTS_PATH, 'data')

    def model_path(self, model):
        return os.path.join(self._models_path, model)

    def data_path(self, file):
        return os.path.join(self._data_path, file)
