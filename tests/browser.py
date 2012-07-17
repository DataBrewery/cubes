import unittest
import os
import cubes
import json
import re

from cubes.browser import PointCut, RangeCut, SetCut, Cell
from cubes.errors import *

from common import DATA_PATH

class BrowserTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        self.model = cubes.model_from_path(self.model_path)
        self.cube = self.model.cube("contracts")

class AggregationBrowserTestCase(BrowserTestCase):
    def setUp(self):
        super(AggregationBrowserTestCase, self).setUp()
        self.browser = cubes.AggregationBrowser(self.cube)

    def test_basics(self):
        dim = self.browser.dimension_object("date")
        self.assertEqual(cubes.Dimension, dim.__class__)

    def test_cutting(self):
        full_cube = self.browser.full_cube()
        self.assertEqual(self.cube, full_cube.cube)
        self.assertEqual(0, len(full_cube.cuts))

        cell = full_cube.slice(cubes.PointCut("date", [2010]))
        self.assertEqual(1, len(cell.cuts))

        cell = cell.slice(cubes.PointCut("supplier", [1234]))
        cell = cell.slice(cubes.PointCut("cpv", [50, 20]))
        self.assertEqual(3, len(cell.cuts))
        self.assertEqual(self.cube, cell.cube)

        # Adding existing slice should result in changing the slice properties
        cell = cell.slice(cubes.PointCut("date", [2011]))
        self.assertEqual(3, len(cell.cuts))

    def test_multi_slice(self):
        full_cube = self.browser.full_cube()

        cuts_list = (
                cubes.PointCut("date", [2010]), 
                cubes.PointCut("cpv", [50, 20]), 
                cubes.PointCut("supplier", [1234]))

        cell_list = full_cube.multi_slice(cuts_list)
        self.assertEqual(3, len(cell_list.cuts))

        self.assertRaises(CubesError, full_cube.multi_slice, {})

    def test_get_cell_dimension_cut(self):
        full_cube = self.browser.full_cube()
        cell = full_cube.slice(cubes.PointCut("date", [2010]))
        cell = cell.slice(cubes.PointCut("supplier", [1234]))

        cut = cell.cut_for_dimension("date")
        self.assertEqual(str(cut.dimension), "date")

        self.assertRaises(cubes.NoSuchDimensionError, cell.cut_for_dimension, "someunknown")
        
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
        
        self.assertRaises(ArgumentError, hier.levels_for_path, [1,2,3,4,5,6,7,8])
        
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
        self.assertRaises(ArgumentError, hier.rollup, path,"detail")
        
    def test_cut_from_dict(self):
        # d = {"type":"point", "path":[2010]}
        # self.assertRaises(Exception, cubes.cut_from_dict, d)
        
        d = {"type":"point", "path":[2010], "dimension":"date", "level_depth":1}
        cut = cubes.cut_from_dict(d)
        tcut = cubes.PointCut("date", [2010])
        self.assertEqual(tcut, cut)
        self.assertEqual(d, tcut.to_dict())

        d = {"type":"range", "from":[2010], "to":[2012, 10], "dimension":"date", "level_depth":2}
        cut = cubes.cut_from_dict(d)
        tcut = cubes.RangeCut("date", [2010], [2012, 10])
        self.assertEqual(tcut, cut)
        self.assertEqual(d, tcut.to_dict())

        d = {"type":"set", "paths":[[2010], [2012, 10]], "dimension":"date", "level_depth":2}
        cut = cubes.cut_from_dict(d)
        tcut = cubes.SetCut("date", [[2010], [2012, 10]])
        self.assertEqual(tcut, cut)
        self.assertEqual(d, tcut.to_dict())
        
    def test_cut_string(self):
        cut = cubes.browser.PointCut("foo", ["10"])
        self.assertEqual("foo:10", str(cut))
        self.assertEqual(cut, cubes.cut_from_string("foo", "10"))

        cut = cubes.browser.PointCut("foo", ["123_abc_", "10", "_"])
        self.assertEqual("foo:123_abc_,10,_", str(cut))
        self.assertEqual(cut, cubes.cut_from_string("foo", "123_abc_,10,_"))

        cut = cubes.browser.PointCut("foo", ["123_ abc_"])
        self.assertRaises(Exception, cut.__str__)

        cut = cubes.browser.PointCut("foo", ["a-b"])
        self.assertRaises(Exception, cut.__str__)

        cut = cubes.browser.PointCut("foo", ["a+b"])
        self.assertRaises(Exception, cut.__str__)
        
    def test_string_from_path(self):
        self.assertEqual('qwe,asd,100', cubes.browser.string_from_path(["qwe", "asd",100]))
        self.assertEqual('', cubes.browser.string_from_path([]))
        self.assertEqual('', cubes.browser.string_from_path(None))

    def test_path_from_string(self):
        self.assertEqual(["qwe", "asd","100"], cubes.browser.path_from_string('qwe,asd,100'))
        self.assertEqual([], cubes.browser.path_from_string(''))
        self.assertEqual([], cubes.browser.path_from_string(None))
        
    def test_set_cut_string(self):

        cut = cubes.browser.SetCut("foo", [["1"], ["2","3"], ["qwe", "asd", "100"]])
        self.assertEqual("foo:1+2,3+qwe,asd,100", str(cut))
        self.assertEqual(cut, cubes.cut_from_string("foo", "1+2,3+qwe,asd,100"))

        cut = cubes.browser.SetCut("foo", ["a+b"])
        self.assertRaises(Exception, cut.__str__)

        cut = cubes.browser.SetCut("foo", ["a-b"])
        self.assertRaises(Exception, cut.__str__)

    def test_range_cut_string(self):
        cut = cubes.browser.RangeCut("date", ["2010"], ["2011"])
        self.assertEqual("date:2010-2011", str(cut))
        self.assertEqual(cut, cubes.cut_from_string("date", "2010-2011"))

        cut = cubes.browser.RangeCut("date", ["2010"], None)
        self.assertEqual("date:2010-", str(cut))
        cut = cubes.cut_from_string("date", "2010-")
        if cut.to_path:
            self.fail('there should be no to path, is: %s' % (cut.to_path, ))

        cut = cubes.browser.RangeCut("date", None, ["2010"])
        self.assertEqual("date:-2010", str(cut))
        cut = cubes.cut_from_string("date", "-2010")
        if cut.from_path:
            self.fail('there should be no from path is: %s' % (cut.from_path, ))

        cut = cubes.browser.RangeCut("date", ["2010","11","12"], ["2011","2","3"])
        self.assertEqual("date:2010,11,12-2011,2,3", str(cut))
        self.assertEqual(cut, cubes.cut_from_string("date", "2010,11,12-2011,2,3"))

        cut = cubes.browser.RangeCut(None, ["a+b"], ["1"])
        self.assertRaises(Exception, cut.__str__)

        cut = cubes.browser.RangeCut("foo", ["a-b"], ["1"])
        self.assertRaises(Exception, cut.__str__)

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

def test_suite():
    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(AggregationBrowserTestCase))
    suite.addTest(unittest.makeSuite(CellsAndCutsTestCase))

    return suite
