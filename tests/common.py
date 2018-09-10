# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import json
import os
import unittest

from sqlalchemy import create_engine, MetaData


TESTS_PATH = os.path.dirname(os.path.abspath(__file__))


class CubesTestCaseBase(unittest.TestCase):
    sql_engine = None

    def setUp(self):
        self._models_path = os.path.join(TESTS_PATH, 'models')

        if self.sql_engine:
            self.engine = create_engine(self.sql_engine)
            self.metadata = MetaData(bind=self.engine)
        else:
            self.engine = None
            self.metadata = None

    def model_path(self, model):
        return os.path.join(self._models_path, model)

    def model_metadata(self, model):
        path = self.model_path(model)
        with open(path) as f:
            md = json.load(f)
        return md
