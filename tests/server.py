import unittest
from cubes import __version__
import json
from .common import CubesTestCaseBase
<<<<<<< HEAD
from sqlalchemy import Table, Column, Integer
=======
>>>>>>> 090c3d55da495f2d3f14cd5085863fb52de0f837

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse

from cubes.server import Slicer

class SlicerTestCaseBase(CubesTestCaseBase):
    def setUp(self):
        super(SlicerTestCaseBase, self).setUp()

        self.slicer = Slicer()
        self.server = Client(self.slicer, BaseResponse)
        self.logger = self.slicer.logger
        self.logger.setLevel("DEBUG")

    def get(self, path, *args, **kwargs):
        if not path.startswith("/"):
            path = "/" + path

        response = self.server.get(path, *args, **kwargs)
        self.logger.debug("response: %s" % response.data)
        try:
            result = json.loads(response.data)
        except ValueError:
            result = None

        return (result, response.status_code)

    def assertHasKeys(self, d, keys):
        for key in keys:
            self.assertIn(key, d)


class SlicerTestCase(SlicerTestCaseBase):
    def test_version(self):
        response, status = self.get("version")
        self.assertEqual(200, status)
        self.assertIsInstance(response, dict)
        self.assertIn("version", response)
        self.assertEqual(__version__, response["version"])

    def test_unknown(self):
        response, status = self.get("this_is_unknown")
        self.assertEqual(404, status)

class SlicerModelTestCase(SlicerTestCaseBase):
    sql_engine = "sqlite:///"

    def setUp(self):
        super(SlicerModelTestCase, self).setUp()

        ws = self.create_workspace()
        self.slicer.workspace = ws

        # Satisfy browser with empty tables
        # TODO: replace this once we have data
        store = ws.get_store("default")
        table = Table("sales", store.metadata)
        table.append_column(Column("id", Integer))
        table.create()

        ws.add_model(self.model_path("model.json"))
        ws.add_model(self.model_path("sales_no_date.json"))

    def test_cube_list(self):
        response, status = self.get("cubes")
        self.assertIsInstance(response, list)
        self.assertEqual(2, len(response))

        for info in response:
            self.assertIn("name", info)
            self.assertIn("label", info)
            self.assertNotIn("dimensions", info)

        names = [c["name"] for c in response]
        self.assertItemsEqual(["contracts", "sales"], names)

    def test_no_cube(self):
        response, status = self.get("cube/unknown_cube/model")
        self.assertEqual(404, status)
        self.assertIsInstance(response, dict)
        self.assertIn("error", response)
        self.assertRegexpMatches(response["error"]["message"], "Unknown cube")

    def test_get_cube(self):
        response, status = self.get("cube/sales/model")
        self.assertEqual(200, status)
        self.assertIsInstance(response, dict)
        self.assertNotIn("error", response)

        self.assertIn("name", response)
        self.assertIn("measures", response)
        self.assertIn("aggregates", response)
        self.assertIn("dimensions", response)

        # We should not get internal info
        self.assertNotIn("mappings", response)
        self.assertNotIn("joins", response)
        self.assertNotIn("options", response)
        self.assertNotIn("browser_options", response)
        self.assertNotIn("fact", response)

        # Propert content
        aggregates = response["aggregates"]
        self.assertIsInstance(aggregates, list)
        self.assertEqual(4, len(aggregates))
        names = [a["name"] for a in aggregates]
        self.assertItemsEqual(["amount_sum", "amount_min", "discount_sum",
                               "record_count"], names)

    def test_cube_dimensions(self):
        response, status = self.get("cube/sales/model")
        # Dimensions
        dims = response["dimensions"]
        self.assertIsInstance(dims, list)
        self.assertIsInstance(dims[0], dict)

        for dim in dims:
            self.assertIn("name", dim)
            self.assertIn("levels", dim)
            self.assertIn("default_hierarchy_name", dim)
            self.assertIn("hierarchies", dim)
            self.assertIn("is_flat", dim)
            self.assertIn("has_details", dim)

        names = [d["name"] for d in dims]
        self.assertItemsEqual(["date", "flag", "product"], names)

        # Test dim flags
        self.assertEqual(True, dims[1]["is_flat"])
        self.assertEqual(False, dims[1]["has_details"])

        self.assertEqual(False, dims[0]["is_flat"])
        self.assertEqual(True, dims[0]["has_details"])
