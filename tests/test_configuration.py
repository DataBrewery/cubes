import os
from cubes.configuration import EnvironmentConfigParser, EnvironmentVariableMissingError

from .common import CubesTestCaseBase


fn = os.path.join('fixtures', 'procurements.ini')
class ConfigurationTestCase(CubesTestCaseBase):
    def setUp(self):
        CubesTestCaseBase.setUp(self)
        self.c = EnvironmentConfigParser()
        self.url = 'sqlite:///procurements.sqlite'
        self.c.read(fn)

    def test_interpolation(self):
        os.environ['DATABASE_URL'] = self.url
        self.assertEqual(self.c['store']['url'], self.url)
        del(os.environ['DATABASE_URL'])

    def test_no_interpolation(self):
        self.assertEqual(self.c['store']['type'], 'sql')

    def test_interpolation_error(self):
        with self.assertRaises(EnvironmentVariableMissingError):
            self.c['store']['url']
