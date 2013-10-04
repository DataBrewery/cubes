import unittest
from cubes import __version__
import json
from .common import CubesTestCaseBase

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
    def setUp(self):
        super(SlicerModelTestCase, self).setUp()

        workspace = self.slicer.workspace
        workspace.add_model(self.model_path("model.json"))
        workspace.add_model(self.model_path("sales_no_date.json"))


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

