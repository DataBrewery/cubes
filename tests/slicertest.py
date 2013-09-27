from cubes.workspace import create_slicer_workspace
from cubes.errors import *
import cubes.browser

w = create_slicer_workspace("http://localhost:5010/")

cube_list = w.list_cubes()

def first_date_dim(cube):
    for d in cube.dimensions:
        if ( d.info.get('is_date') ):
            return d
    raise BrowserError("No date dimension in cube %s" % cube.name)

for c in cube_list:
    print ("Doing %s..." % c.get('name')),
    cube = w.cube(c.get('name'))
    date_dim = first_date_dim(cube)
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

