import unittest
from cubes import __version__
import json

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse

from cubes.server import Slicer

class SlicerTestCase(unittest.TestCase):
    def setUp(self):
        self.slicer = Slicer()
        self.server = Client(self.slicer, BaseResponse)
        self.logger = self.slicer.logger
        self.logger.setLevel("DEBUG")

    def get(self, *args, **kwargs):
        response = self.server.get(*args, **kwargs)
        self.logger.debug("response: %s" % response.data)
        try:
            result = json.loads(response.data)
        except ValueError:
            result = None

        return (result, response.status_code)

    def assertHasKeys(self, d, keys):
        for key in keys:
            self.assertIn(key, d)

    def test_version(self):
        response, status = self.get("/version")
        self.assertEqual(200, status)
        self.assertIsInstance(response, dict)
        self.assertIn("version", response)
        self.assertEqual(__version__, response["version"])

    def test_unknown(self):
        response, status = self.get("/this_is_unknown")
        self.assertEqual(404, status)

