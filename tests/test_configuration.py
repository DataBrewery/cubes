import os
from cubes.configuration import EnvironmentConfigParser

from .common import CubesTestCaseBase


fn = os.path.join('fixtures', 'procurements.ini')
class ConfigurationTestCase(CubesTestCaseBase):
    def setUp(self):
        CubesTestCaseBase.setUp(self)
        self.c = EnvironmentConfigParser()
        self.url = 'sqlite:///procurements.sqlite'

    def test_interpolation(self):
        os.environ['DATABASE_URL'] = self.url
        self.c.read(fn)
        self.assertEqual(self.c['store']['url'], self.url)
        del(os.environ['DATABASE_URL'])

    def test_no_interpolation(self):
        self.c.read(fn)
        self.assertEqual(self.c['store']['type'], 'sql')

    def test_interpolation_error(self):
        # self.assertRaises
        c['store']['url']
        assert False
