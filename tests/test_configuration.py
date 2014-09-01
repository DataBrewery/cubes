import os
from cubes.configuration import EnvironmentConfigParser

from .common import CubesTestCaseBase


class ConfigurationTestCase(CubesTestCaseBase):
    def setUp(self):
        CubesTestCaseBase.setUp(self)
        fn = os.path.join('fixtures', 'procurements.ini')
        self.c = EnvironmentConfigParser()
        self.c.read(fn)
        self.url = 'sqlite:///procurements.sqlite'

    def test_interpolation(self):
        os.environ['DATABASE_URL'] = self.url
        self.assertEqual(c['store']['url'], self.url)
        del(os.environ['DATABASE_URL'])

    def test_no_interpolation(self):
        self.assertEqual(c['store']['type'], 'sql')

    def test_interpolation_error(self):
        # self.assertRaises
        c['store']['url']
        assert False
