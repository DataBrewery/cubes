import unittest

from cubes.cells import Cell, PointCut, SetCut, RangeCut
from cubes.cells import string_from_path, cut_from_string, path_from_string
from cubes.cells import cut_from_dict
from cubes.errors import CubesError, ArgumentError
from cubes.errors import HierarchyError, NoSuchDimensionError

from .common import CubesTestCaseBase, create_provider


class CutsTestCase(CubesTestCaseBase):
    def setUp(self):
        super(CutsTestCase, self).setUp()

        self.provider = create_provider("browser_test.json")
        self.cube = self.provider.cube("transactions")
        self.dim_date = self.cube.dimension("date")

    def test_cut_depth(self):
        dim = self.cube.dimension("date")
        self.assertEqual(1, PointCut(dim, [1]).level_depth())
        self.assertEqual(3, PointCut(dim, [1, 1, 1]).level_depth())
        self.assertEqual(1, RangeCut(dim, [1], [1]).level_depth())
        self.assertEqual(3, RangeCut(dim, [1, 1, 1], [1]).level_depth())
        self.assertEqual(1, SetCut(dim, [[1], [1]]).level_depth())
        self.assertEqual(3, SetCut(dim, [[1], [1], [1, 1, 1]]).level_depth())

    def test_cut_from_dict(self):
        # d = {"type":"point", "path":[2010]}
        # self.assertRaises(Exception, cubes.cut_from_dict, d)

        d = {"type": "point", "path": [2010], "dimension": "date",
             "level_depth": 1, "hierarchy": None, "invert": False,
             "hidden": False}

        cut = cut_from_dict(d)
        tcut = PointCut("date", [2010])
        self.assertEqual(tcut, cut)
        self.assertEqual(dict(d), tcut.to_dict())
        self._assert_invert(d, cut, tcut)

        d = {"type": "range", "from": [2010], "to": [2012, 10], "dimension":
             "date", "level_depth": 2, "hierarchy": None, "invert": False,
             "hidden": False}
        cut = cut_from_dict(d)
        tcut = RangeCut("date", [2010], [2012, 10])
        self.assertEqual(tcut, cut)
        self.assertEqual(dict(d), tcut.to_dict())
        self._assert_invert(d, cut, tcut)

        d = {"type": "set", "paths": [[2010], [2012, 10]], "dimension": "date",
             "level_depth": 2, "hierarchy": None, "invert": False,
             "hidden": False}
        cut = cut_from_dict(d)
        tcut = SetCut("date", [[2010], [2012, 10]])
        self.assertEqual(tcut, cut)
        self.assertEqual(dict(d), tcut.to_dict())
        self._assert_invert(d, cut, tcut)

        self.assertRaises(ArgumentError, cut_from_dict, {"type": "xxx"})

    def _assert_invert(self, d, cut, tcut):
        cut.invert = True
        tcut.invert = True
        d["invert"] = True
        self.assertEqual(tcut, cut)
        self.assertEqual(dict(d), tcut.to_dict())


class StringConversionsTestCase(unittest.TestCase):
    def test_cut_string_conversions(self):
        cut = PointCut("foo", ["10"])
        self.assertEqual("foo:10", str(cut))
        self.assertEqual(cut, cut_from_string("foo:10"))

        cut = PointCut("foo", ["123_abc_", "10", "_"])
        self.assertEqual("foo:123_abc_,10,_", str(cut))
        self.assertEqual(cut, cut_from_string("foo:123_abc_,10,_"))

        cut = PointCut("foo", ["123_ abc_"])
        self.assertEqual(r"foo:123_ abc_", str(cut))
        self.assertEqual(cut, cut_from_string("foo:123_ abc_"))

        cut = PointCut("foo", ["a-b"])
        self.assertEqual("foo:a\-b", str(cut))
        self.assertEqual(cut, cut_from_string("foo:a\-b"))

        cut = PointCut("foo", ["a+b"])
        self.assertEqual("foo:a+b", str(cut))
        self.assertEqual(cut, cut_from_string("foo:a+b"))

    def test_special_characters(self):
        self.assertEqual('\\:q\\-we,a\\\\sd\\;,100',
                         string_from_path([":q-we", "a\\sd;", 100]))

    def test_string_from_path(self):
        self.assertEqual('qwe,asd,100',
                         string_from_path(["qwe", "asd", 100]))
        self.assertEqual('', string_from_path([]))
        self.assertEqual('', string_from_path(None))

    def test_path_from_string(self):
        self.assertEqual(["qwe", "asd", "100"],
                         path_from_string('qwe,asd,100'))
        self.assertEqual([], path_from_string(''))
        self.assertEqual([], path_from_string(None))

    def test_set_cut_string(self):

        cut = SetCut("foo", [["1"], ["2", "3"], ["qwe", "asd", "100"]])
        self.assertEqual("foo:1;2,3;qwe,asd,100", str(cut))
        self.assertEqual(cut, cut_from_string("foo:1;2,3;qwe,asd,100"))

        # single-element SetCuts cannot go round trip, they become point cuts
        cut = SetCut("foo", [["a+b"]])
        self.assertEqual("foo:a+b", str(cut))
        self.assertEqual(PointCut("foo", ["a+b"]), cut_from_string("foo:a+b"))

        cut = SetCut("foo", [["a-b"]])
        self.assertEqual("foo:a\-b", str(cut))
        self.assertEqual(PointCut("foo", ["a-b"]), cut_from_string("foo:a\-b"))

    def test_range_cut_string(self):
        cut = RangeCut("date", ["2010"], ["2011"])
        self.assertEqual("date:2010-2011", str(cut))
        self.assertEqual(cut, cut_from_string("date:2010-2011"))

        cut = RangeCut("date", ["2010"], None)
        self.assertEqual("date:2010-", str(cut))
        cut = cut_from_string("date:2010-")
        if cut.to_path:
            self.fail('there should be no to path, is: %s' % (cut.to_path, ))

        cut = RangeCut("date", None, ["2010"])
        self.assertEqual("date:-2010", str(cut))
        cut = cut_from_string("date:-2010")
        if cut.from_path:
            self.fail('there should be no from path is: %s' % (cut.from_path, ))

        cut = RangeCut("date", ["2010", "11", "12"], ["2011", "2", "3"])
        self.assertEqual("date:2010,11,12-2011,2,3", str(cut))
        self.assertEqual(cut, cut_from_string("date:2010,11,12-2011,2,3"))

        cut = RangeCut("foo", ["a+b"], ["1"])
        self.assertEqual("foo:a+b-1", str(cut))
        self.assertEqual(cut, cut_from_string("foo:a+b-1"))

        cut = RangeCut("foo", ["a-b"], ["1"])
        self.assertEqual(r"foo:a\-b-1", str(cut))
        self.assertEqual(cut, cut_from_string(r"foo:a\-b-1"))

    def test_hierarchy_cut(self):
        cut = PointCut("date", ["10"], "dqmy")
        self.assertEqual("date@dqmy:10", str(cut))
        self.assertEqual(cut, cut_from_string("date@dqmy:10"))


class CellInteractiveSlicingTestCase(CubesTestCaseBase):
    def setUp(self):
        super(CellInteractiveSlicingTestCase, self).setUp()

        self.provider = create_provider("model.json")
        self.cube = self.provider.cube("contracts")

    def test_cutting(self):
        full_cube = Cell(self.cube)
        self.assertEqual(self.cube, full_cube.cube)
        self.assertEqual(0, len(full_cube.cuts))

        cell = full_cube.slice(PointCut("date", [2010]))
        self.assertEqual(1, len(cell.cuts))

        cell = cell.slice(PointCut("supplier", [1234]))
        cell = cell.slice(PointCut("cpv", [50, 20]))
        self.assertEqual(3, len(cell.cuts))
        self.assertEqual(self.cube, cell.cube)

        # Adding existing slice should result in changing the slice properties
        cell = cell.slice(PointCut("date", [2011]))
        self.assertEqual(3, len(cell.cuts))

    def test_multi_slice(self):
        full_cube = Cell(self.cube)

        cuts_list = (
            PointCut("date", [2010]),
            PointCut("cpv", [50, 20]),
            PointCut("supplier", [1234]))

        cell_list = full_cube.multi_slice(cuts_list)
        self.assertEqual(3, len(cell_list.cuts))

        self.assertRaises(CubesError, full_cube.multi_slice, {})

    def test_get_cell_dimension_cut(self):
        full_cube = Cell(self.cube)
        cell = full_cube.slice(PointCut("date", [2010]))
        cell = cell.slice(PointCut("supplier", [1234]))

        cut = cell.cut_for_dimension("date")
        self.assertEqual(str(cut.dimension), "date")

        self.assertRaises(NoSuchDimensionError, cell.cut_for_dimension, "someunknown")

        cut = cell.cut_for_dimension("cpv")
        self.assertEqual(cut, None)

    def test_hierarchy_path(self):
        dim = self.cube.dimension("cpv")
        hier = dim.hierarchy()

        levels = hier.levels_for_path([])
        self.assertEqual(len(levels), 0)
        levels = hier.levels_for_path(None)
        self.assertEqual(len(levels), 0)

        levels = hier.levels_for_path([1, 2, 3, 4])
        self.assertEqual(len(levels), 4)
        names = [level.name for level in levels]
        self.assertEqual(names, ['division', 'group', 'class', 'category'])

        self.assertRaises(HierarchyError, hier.levels_for_path,
                          [1, 2, 3, 4, 5, 6, 7, 8])

    def test_hierarchy_drilldown_levels(self):
        dim = self.cube.dimension("cpv")
        hier = dim.hierarchy()

        levels = hier.levels_for_path([], drilldown=True)
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].name, 'division')
        levels = hier.levels_for_path(None, drilldown=True)
        self.assertEqual(len(levels), 1)
        self.assertEqual(levels[0].name, 'division')

    def test_slice_drilldown(self):
        cut = PointCut("date", [])
        original_cell = Cell(self.cube, [cut])

        cell = original_cell.drilldown("date", 2010)
        self.assertEqual([2010], cell.cut_for_dimension("date").path)

        cell = cell.drilldown("date", 1)
        self.assertEqual([2010, 1], cell.cut_for_dimension("date").path)

        cell = cell.drilldown("date", 2)
        self.assertEqual([2010, 1, 2], cell.cut_for_dimension("date").path)


def test_suite():
    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(AggregationBrowserTestCase))
    suite.addTest(unittest.makeSuite(CellsAndCutsTestCase))

    return suite
