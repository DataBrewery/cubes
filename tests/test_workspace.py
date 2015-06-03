import unittest
import os
import json
import re
from cubes.errors import NoSuchCubeError, NoSuchDimensionError
from cubes.errors import NoSuchAttributeError
from cubes.workspace import Workspace
from cubes.stores import Store
from cubes.model import *

from .common import CubesTestCaseBase
# FIXME: remove this once satisfied

class WorkspaceTestCaseBase(CubesTestCaseBase):
    def default_workspace(self, model_name=None):
        model_name = model_name or "model.json"
        ws = Workspace(config=self.data_path("slicer.ini"))
        ws.import_model(self.model_path("model.json"))
        return ws


class WorkspaceModelTestCase(WorkspaceTestCaseBase):
    def test_get_cube(self):
        ws = self.default_workspace()
        cube = ws.cube("contracts")

        self.assertEqual("contracts", cube.name)
        # self.assertEqual(6, len(cube.dimensions))
        self.assertEqual(1, len(cube.measures))

    def test_get_namespace_cube(self):
        ws = Workspace()
        ws.import_model(self.model_path("model.json"), namespace="local")

        with self.assertRaises(NoSuchCubeError):
            cube = ws.cube("contracts")

        cube = ws.cube("local.contracts")
        self.assertEqual("local.contracts", cube.name)

    def test_cube_with_dimensions_in_two_namespaces(self):
        ws = Workspace()
        ws.import_model(self.model_path("model.json"), namespace="store1")
        ws.import_model(self.model_path("other.json"), namespace="store2")

        # This should not pass, since the dimension is in another namespace
        with self.assertRaises(NoSuchDimensionError):
            ws.cube("store2.other")

        ws = Workspace()
        ws.import_model(self.model_path("model.json"), namespace="default")
        ws.import_model(self.model_path("other.json"), namespace="store2")

        # This should pass, since the dimension is in the default namespace
        ws.cube("store2.other")

    def test_get_dimension(self):
        ws = self.default_workspace()
        dim = ws.dimension("date")
        self.assertEqual("date", dim.name)

    def test_template(self):
        ws = Workspace()
        ws.import_model(self.model_path("templated_dimension.json"))

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
        ws.import_model(self.model_path("templated_dimension.json"))
        ws.import_model(self.model_path("templated_dimension_ext.json"))

        dim = ws.dimension("another_date")
        self.assertEqual("another_date", dim.name)
        self.assertEqual(3, len(dim.levels))

    @unittest.skip("We are lazy now, we don't want to ping the provider for "
                   "nothing")
    def test_duplicate_dimension(self):
        ws = Workspace()
        ws.import_model(self.model_path("templated_dimension.json"))

        model = {"dimensions": [{"name": "date"}]}
        with self.assertRaises(ModelError):
            ws.import_model(model)

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

