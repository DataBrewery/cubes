import unittest
import os

from cubes.workspace import create_slicer_workspace
from cubes.errors import *
import cubes.browser

@unittest.skipIf("TEST_SLICER" not in os.environ,
                 "No TEST_SLICER environment variable set.")

class SlicerTestCase(unittest.TestCase):
    def setUp(self):
        self.w = create_slicer_workspace("http://localhost:5010/")

        self.cube_list = self.w.list_cubes()

    def first_date_dim(self, cube):
        for d in cube.dimensions:
            if ( d.info.get('is_date') ):
                return d
        raise BrowserError("No date dimension in cube %s" % cube.name)

    def test_basic(self):
        for c in self.cube_list:
            print ("Doing %s..." % c.get('name')),
            cube = self.w.cube(c.get('name'))
            date_dim = self.first_date_dim(cube)
            cut = cubes.browser.RangeCut(date_dim, [ 2013, 9, 25 ], None)
            cell = cubes.browser.Cell(cube, [ cut ])
            drill = cubes.browser.Drilldown([(date_dim, None, date_dim.level('day'))], cell)
            b = w.browser(cube)
            try:
                attr_dim = cube.dimension("attr")
                split = cubes.browser.PointCut(attr_dim, ['paid', 'pnb'])
            except:
                split = None
            try:
                result = b.aggregate(cell, drilldown=drill, split=split, measure=cube.measures[0])
                print result.cells
            except:
                import sys
                print sys.exc_info()

