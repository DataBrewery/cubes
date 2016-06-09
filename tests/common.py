import os
import unittest
from cubes import Workspace
from cubes import compat
from sqlalchemy import create_engine, MetaData
import json
from cubes.metadata import read_model_metadata
from cubes.metadata import StaticModelProvider

TESTS_PATH = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(TESTS_PATH, 'data')

def create_provider(name):
    # TODO: this should be rather:
    # provider = FileModelProvider(path)
    path = os.path.join(TESTS_PATH, 'models', name)
    metadata = read_model_metadata(path)
    return StaticModelProvider(metadata)

class CubesTestCaseBase(unittest.TestCase):
    sql_engine = None

    def setUp(self):
        self._models_path = os.path.join(TESTS_PATH, 'models')
        self._data_path = os.path.join(TESTS_PATH, 'data')

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

    def data_path(self, file):
        return os.path.join(self._data_path, file)

    def create_workspace(self, store=None, model=None):
        """Create shared workspace. Add default store specified in `store` as
        a dictionary and `model` which can be a filename relative to
        ``tests/models`` or a moel dictionary. If no store is provided but
        class has an engine or `sql_engine` set, then the existing engine will
        be used as the default SQL store."""

        raise NotImplementedError("Depreciated in this context")
        workspace = Workspace()

        if store:
            store = dict(store)
            store_type = store.pop("type", "sql")
            workspace.register_default_store(store_type, **store)
        elif self.engine:
            workspace.register_default_store("sql", engine=self.engine)

        if model:
            if isinstance(model, compat.string_type):
                model = self.model_path(model)
            workspace.import_model(model)

        return workspace

    def load_data(self, table, data):
        self.engine.execute(table.delete())
        for row in data:
            insert = table.insert().values(row)
            self.engine.execute(insert)

    if not compat.py3k:
        assertCountEqual = unittest.TestCase.assertItemsEqual

