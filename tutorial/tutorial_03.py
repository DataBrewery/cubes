import sqlalchemy
import cubes
import cubes.tutorial.sql as tutorial
import logging
import copy
        
# In this tutorial you are going to learn how to create a model file and use hierarchies. 
# The example shows:
# 
# * how hierarhies work
# * drill-down through a hierarchy
#
# The example data used are IBRD Balance Sheet taken from The World Bank
# Source: https://raw.github.com/Stiivi/cubes/master/tutorial/data/IBRD_Balance_Sheet__FY2010.csv
# 
# The source data file is manually modified for this tutorial: column "Line Item" is split into two:
# Subcategory and Line Item
#
# Create a tutorial directory and download the file:

# 1. Prepare SQL data in memory

logger = logging.getLogger("cubes")
logger.setLevel(logging.WARN)

FACT_TABLE = "irbd_balance"

engine = sqlalchemy.create_engine('sqlite:///:memory:')
tutorial.create_table_from_csv(engine, 
                      "data/IBRD_Balance_Sheet__FY2010-t03.csv", 
                      table_name=FACT_TABLE, 
                      fields=[
                            ("category", "string"),
                            ("category_label", "string"), 
                            ("subcategory", "string"), 
                            ("subcategory_label", "string"), 
                            ("line_item", "string"),
                            ("year", "integer"), 
                            ("amount", "integer")],
                      create_id=True    
                    )

def drill_down(cell, dimension, path = []):
    """Drill-down and aggregate recursively through all levels of `dimension`.
    
    This function is like recursively traversing directories on a file system and aggregating the
    file sizes, for example.
    
    :Attributes:
    * cell - cube cell to drill-down
    * dimension - dimension to be traversed through all levels
    * path - current path of the `dimension`
    
    Path is list of dimension points (keys) at each level. It is like file-system path.
    """

    # Get dimension's default hierarchy. Cubes supports multiple hierarchies, for example for
    # date you might have year-month-day or year-quarter-month-day. Most dimensions will
    # have one hierarchy, thought.
    hierarchy = dimension.hierarchy()

    # Can we go deeper in the hierarchy? Base path is path to the most detailed element,
    # to the leaf of a tree, to the fact.

    if hierarchy.path_is_base(path):
        return

    # Get the next level in the hierarchy. ``levels_for_pat`` returns list of levels
    # according to provided path. When ``drilldown`` is set to ``True`` then one
    # more level is returned.
        
    levels = hierarchy.levels_for_path(path,drilldown=True)
    current_level = levels[-1]

    # We need to know name of the level key attribute which contains a path component.
    # If the model does not explicitly specify key attribute for the level, then first attribute
    # will be used
    level_key = dimension.attribute_reference(current_level.key)

    # For prettier display, we get name of attribute which contains label to be displayed
    # for the current level. If there is no label attribute, then key attribute is used.
    level_label = dimension.attribute_reference(current_level.label_attribute)

    # Just visual formatting - indentation based on path lenght.
    indent = "    " * len(path)

    # We do the aggregation of the cell... Think of ``ls $CELL`` command in commandline, where `$CELL`
    # is a directory name. In this function we can think of ``$CELL`` to be same as current working
    # directory (pwd)
    result = browser.aggregate(cell, drilldown=[dimension])

    # ... and display the results
    # print "%s==Level: %s==" % (indent, current_level.label)

    for record in result.drilldown:
        print "%s%s: %d" % (indent, record[level_label], record["record_count"])

        # Construct new path: current path with key attribute value appended
        drill_path = path[:] + [record[level_key]]

        # Get a new cell slice for current path
        drill_down_cell = cell.slice(cubes.PointCut(dimension, drill_path))

        # And do recursive drill-down
        drill_down(drill_down_cell, dimension, drill_path)

# 2. Load model and get cube of our interest

model = cubes.load_model("models/model_03.json")
cube = model.cube("irbd_balance")

# 3. Create a browser

workspace = cubes.create_workspace("sql.star", model, engine=engine)
browser = workspace.browser(cube)

# Get whole cube
cell = browser.full_cube()

print "Drill down through all item levels:"
drill_down(cell, cube.dimension("item"))

print "Drill down through all item for year 2010:"
cell = cell.slice(cubes.PointCut("year", [2010]))
drill_down(cell, cube.dimension("item"))
