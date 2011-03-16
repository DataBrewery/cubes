import unittest
import os
import cubes
from cubes.tests import DATA_PATH

class CubeComputationTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        self.model = cubes.model_from_path(self.model_path)
        self.cube = self.model.cubes.get("contracts")

    def test_combine_dimensions(self):
        dims = self.cube.dimensions
        results = cubes.util.compute_dimension_cell_selectors(dims)
        # for r in results:
        #     print "=== COMBO:"
        #     for c in r:
        #         print "---     %s: %s" % (c[0][0].name, c[1])

        self.assertEqual(len(results), 863)

        dim = self.cube.dimension("date")
        results = cubes.util.compute_dimension_cell_selectors(dims, [dim])
        self.assertEqual(len(results), 648)

    def test_should_not_accept_unknown_dimension(self):
        foo_desc = { "name": "foo", "levels": {"level": {"key": "boo"}}}
        foo_dim = cubes.Dimension('foo', foo_desc)

        self.assertRaises(AttributeError, cubes.util.compute_dimension_cell_selectors,
                                          self.cube.dimensions, [foo_dim])

