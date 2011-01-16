import unittest
import os
import cubes
import cubes.tests
import json
import re

class AggregationsBasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(cubes.tests.tests_path, 'model')
        self.model = cubes.model_from_path(self.model_path)
        self.cube = self.model.cubes["contracts"]
        self.browser = cubes.browsers.AggregationBrowser(self.cube)
    
    def test_basics(self):
        dim = self.browser.dimension_object("date")
        self.assertEqual(cubes.Dimension, dim.__class__)
        
    def test_cutting(self):
        full_cube = self.browser.full_cube()
        self.assertEqual(self.cube, full_cube.cube)
        self.assertEqual(0, len(full_cube.cuts))
        
        cuboid = full_cube.slice("date", [2010])
        self.assertEqual(1, len(cuboid.cuts))
        
        cuboid = cuboid.slice("supplier", [1234])
        cuboid = cuboid.slice("cpv", [50, 20])
        self.assertEqual(3, len(cuboid.cuts))
        self.assertEqual(self.cube, cuboid.cube)

        # Adding existing slice should result in changing the slice properties
        cuboid = cuboid.slice("date", [2011])
        self.assertEqual(3, len(cuboid.cuts))

    def test_multi_slice(self):
        full_cube = self.browser.full_cube()

        cuts_list = (("date", [2010]), ("cpv", [50, 20]), ("supplier", [1234]))
        cuts_dict = {"date": [2010], "cpv": [50, 20], "supplier": [1234]}

        cuboid_list = full_cube.multi_slice(cuts_list)
        self.assertEqual(3, len(cuboid_list.cuts))

        cuboid_dict = full_cube.multi_slice(cuts_dict)
        self.assertEqual(3, len(cuboid_dict.cuts))

        self.assertEqual(cuboid_list, cuboid_dict)
