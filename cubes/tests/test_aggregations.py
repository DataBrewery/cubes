import unittest
import os
import cubes
import json
import re

from cubes.tests import DATA_PATH

class AggregationsBasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        self.model = cubes.model_from_path(self.model_path)
        self.cube = self.model.cubes["contracts"]
        self.browser = cubes.AggregationBrowser(self.cube)
    
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

    def test_get_cuboid_dimension_cut(self):
        full_cube = self.browser.full_cube()
        cuboid = full_cube.slice("date", [2010])
        cuboid = cuboid.slice("supplier", [1234])

        cut = cuboid.cut_for_dimension("date")
        self.assertEqual(cut.dimension, self.cube.dimension("date"))

        self.assertRaises(cubes.ModelError, cuboid.cut_for_dimension, "someunknown")
        
        cut = cuboid.cut_for_dimension("cpv")
        self.assertEqual(cut, None)
        
    def test_hierarchy_path(self):
        dim =self.cube.dimension("cpv")
        hier = dim.default_hierarchy

        levels = hier.levels_for_path([])
        self.assertEqual(len(levels), 0)
        levels = hier.levels_for_path(None)
        self.assertEqual(len(levels), 0)

        levels = hier.levels_for_path([1,2,3,4])
        self.assertEqual(len(levels), 4)
        names = [level.name for level in levels]
        self.assertEqual(names, ['division', 'group', 'class', 'category'])
        
        self.assertRaises(AttributeError, hier.levels_for_path, [1,2,3,4,5,6,7,8])
        
    def test_hierarchy_drilldown_levels(self):
        dim =self.cube.dimension("cpv")
        hier = dim.default_hierarchy

        levels = hier.levels_for_path([], drilldown = True)
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].name, 'division')
        levels = hier.levels_for_path(None, drilldown = True)
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].name, 'division')

    def test_hierarchy_rollup(self):
        dim =self.cube.dimension("cpv")
        hier = dim.default_hierarchy

        path = [1,2,3,4]
        
        self.assertEqual([1,2,3], hier.rollup(path))
        self.assertEqual([1], hier.rollup(path,"division"))
        self.assertEqual([1,2], hier.rollup(path,"group"))
        self.assertEqual([1,2,3], hier.rollup(path,"class"))
        self.assertEqual([1,2,3,4], hier.rollup(path,"category"))
        self.assertRaises(ValueError, hier.rollup, path,"detail")
