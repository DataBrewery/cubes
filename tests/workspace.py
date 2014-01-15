import unittest
import os
import json
import re
from cubes.errors import *
from cubes.workspace import *
from cubes.model import *
from cubes.extensions import get_namespace

from common import CubesTestCaseBase
# FIXME: remove this once satisfied

class WorkspaceTestCaseBase(CubesTestCaseBase):
    def default_workspace(self, model_name=None):
        model_name = model_name or "model.json"
        ws = Workspace(config=self.data_path("slicer.ini"))
        ws.add_model(self.model_path("model.json"))
        return ws

class WorkspaceStoresTestCase(WorkspaceTestCaseBase):
    def test_empty(self):
        """Just test whether we can create empty workspace"""
        ws = Workspace()
        self.assertEqual(0, len(ws.store_infos))

    def test_stores(self):
        ws = Workspace(stores={"default":{"type":"imaginary"}})
        self.assertTrue("default" in ws.store_infos)

        ws = Workspace(stores=self.data_path("stores.ini"))
        self.assertEqual(3, len(ws.store_infos) )

        ws = Workspace(config=self.data_path("slicer.ini"))
        self.assertEqual(2, len(ws.store_infos))

        self.assertTrue("default" in ws.store_infos)
        self.assertTrue("production" in ws.store_infos)

    def test_duplicate_store(self):
        with self.assertRaises(CubesError):
            ws = Workspace(config=self.data_path("slicer.ini"),
                           stores=self.data_path("stores.ini"))


class WorkspaceModelTestCase(WorkspaceTestCaseBase):
    def test_get_cube(self):
        ws = self.default_workspace()
        cube = ws.cube("contracts")

        self.assertEqual("contracts", cube.name)
        # self.assertEqual(6, len(cube.dimensions))
        self.assertEqual(1, len(cube.measures))

    def test_get_dimension(self):
        ws = self.default_workspace()
        dim = ws.dimension("date")
        self.assertEqual("date", dim.name)

    def test_template(self):
        ws = Workspace()
        ws.add_model(self.model_path("templated_dimension.json"))

        dim = ws.dimension("date")
        self.assertEqual("date", dim.name)
        self.assertEqual(3, len(dim.levels))

        dim = ws.dimension("start_date")
        self.assertEqual("start_date", dim.name)
        self.assertEqual(3, len(dim.levels))

        dim = ws.dimension("end_date")
        self.assertEqual("end_date", dim.name)

    def test_external_template(self):
        ws = Workspace()
        ws.add_model(self.model_path("templated_dimension.json"))
        ws.add_model(self.model_path("templated_dimension_ext.json"))

        dim = ws.dimension("another_date")
        self.assertEqual("another_date", dim.name)
        self.assertEqual(3, len(dim.levels))

    @unittest.skip("We are lazy now, we don't want to ping the provider for "
                   "nothing")
    def test_duplicate_dimension(self):
        ws = Workspace()
        ws.add_model(self.model_path("templated_dimension.json"))

        model = {"dimensions": [{"name": "date"}]}
        with self.assertRaises(ModelError):
            ws.add_model(model)

    def test_local_dimension(self):
        # Test whether we can use local dimension with the same name as the
        # public one
        ws = Workspace()
        ws.import_model(self.model_path("model_public_dimensions.json"))
        ws.import_model(self.model_path("model_private_dimensions.json"))

        dim = ws.dimension("date")
        self.assertEqual(3, len(dim.levels))
        self.assertEqual(["year", "month", "day"], dim.level_names)


        cube = ws.cube("events")
        dim = cube.dimension("date")
        self.assertEqual(["year", "month", "day"], dim.level_names)

        cube = ws.cube("lonely_yearly_events")
        dim = cube.dimension("date")
        self.assertEqual(["lonely_year"], dim.level_names)

