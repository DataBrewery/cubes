import unittest
import os
import cubes
import json
import re

from cubes.browser import PointCut, RangeCut, SetCut, Cell

from common import DATA_PATH
        
class BrowserTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        self.model = cubes.model_from_path(self.model_path)
        self.cube = self.model.cubes["contracts"]

class AggregationsBasicsTestCase(BrowserTestCase):
    def setUp(self):
        super(AggregationsBasicsTestCase, self).setUp()
        self.browser = cubes.AggregationBrowser(self.cube)
    
    def test_basics(self):
        dim = self.browser.dimension_object("date")
        self.assertEqual(cubes.Dimension, dim.__class__)
        
    def test_cutting(self):
        full_cube = self.browser.full_cube()
        self.assertEqual(self.cube, full_cube.cube)
        self.assertEqual(0, len(full_cube.cuts))
        
        cell = full_cube.slice("date", [2010])
        self.assertEqual(1, len(cell.cuts))
        
        cell = cell.slice("supplier", [1234])
        cell = cell.slice("cpv", [50, 20])
        self.assertEqual(3, len(cell.cuts))
        self.assertEqual(self.cube, cell.cube)

        # Adding existing slice should result in changing the slice properties
        cell = cell.slice("date", [2011])
        self.assertEqual(3, len(cell.cuts))

    def test_multi_slice(self):
        full_cube = self.browser.full_cube()

        cuts_list = (("date", [2010]), ("cpv", [50, 20]), ("supplier", [1234]))
        cuts_dict = {"date": [2010], "cpv": [50, 20], "supplier": [1234]}

        cell_list = full_cube.multi_slice(cuts_list)
        self.assertEqual(3, len(cell_list.cuts))

        cell_dict = full_cube.multi_slice(cuts_dict)
        self.assertEqual(3, len(cell_dict.cuts))

        self.assertEqual(cell_list, cell_dict)

    def test_get_cell_dimension_cut(self):
        full_cube = self.browser.full_cube()
        cell = full_cube.slice("date", [2010])
        cell = cell.slice("supplier", [1234])

        cut = cell.cut_for_dimension("date")
        self.assertEqual(cut.dimension, self.cube.dimension("date"))

        self.assertRaises(cubes.ModelError, cell.cut_for_dimension, "someunknown")
        
        cut = cell.cut_for_dimension("cpv")
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
        
    def test_set_cut_string(self):
        cut = cubes.browser.SetCut("date", [[1], [2,3], ["qwe", "asd",100]])
        
        self.assertEqual('qwe,asd,100', cubes.browser.string_from_path(["qwe", "asd",100]))
        self.assertEqual("date:1+2,3+qwe,asd,100", str(cut))

    def test_slice_drilldown(self):
        cut = cubes.browser.PointCut("date", [])
        original_cell = cubes.Cell(self.cube, [cut])

        cell = original_cell.drilldown("date", 2010)
        self.assertEqual([2010], cell.cut_for_dimension("date").path)

        cell = cell.drilldown("date", 1)
        self.assertEqual([2010,1], cell.cut_for_dimension("date").path)

        cell = cell.drilldown("date", 2)
        self.assertEqual([2010,1,2], cell.cut_for_dimension("date").path)

class CellsAndCutsTestCase(BrowserTestCase):
    def setUp(self):
        super(CellsAndCutsTestCase, self).setUp()
    
    def test_cut_depth(self):
        dim = self.cube.dimension("date")
        self.assertEqual(1, PointCut(dim, [1]).level_depth())
        self.assertEqual(3, PointCut(dim, [1,1,1]).level_depth())
        self.assertEqual(1, RangeCut(dim, [1],[1]).level_depth())
        self.assertEqual(3, RangeCut(dim, [1,1,1],[1]).level_depth())
        self.assertEqual(1, SetCut(dim, [[1],[1]]).level_depth())
        self.assertEqual(3, SetCut(dim, [[1],[1],[1,1,1]]).level_depth())

def suite():
    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(AggregationsBasicsTestCase))
    suite.addTest(unittest.makeSuite(CellsAndCutsTestCase))

    return suite
