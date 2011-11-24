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

FACT_TABLE = "ft_irbd_balance"
FACT_VIEW = "vft_irbd_balance"

engine = sqlalchemy.create_engine('sqlite:///:memory:')
tutorial.create_table_from_csv(engine, 
                      "data/IBRD_Balance_Sheet__FY2010-t02.csv", 
                      table_name=FACT_TABLE, 
                      fields=[
                            ("category", "string"), 
                            ("subcategory", "string"), 
                            ("line_item", "string"),
                            ("year", "integer"), 
                            ("amount", "integer")],
                      create_id=True    
                        
                        )

model = cubes.load_model("models/model_02.json")

cube = model.cube("irbd_balance")
cube.fact = FACT_TABLE

# 4. Create a browser and get a cell representing the whole cube (all data)

connection = engine.connect()
dn = cubes.backends.sql.SQLDenormalizer(cube, connection)

dn.create_view(FACT_VIEW)

def drill_down(cell, dimension, path = []):
    hierarchy = dimension.default_hierarchy

    if hierarchy.path_is_base(path):
        return


    levels = hierarchy.levels_for_path(path,drilldown=True)
    current_level = levels[-1]

    level_label = dimension.attribute_reference(current_level.label_attribute)
    level_key = dimension.attribute_reference(current_level.key)

    indent = "----" * len(path)

    result = browser.aggregate(cell, drilldown=[dimension])

    for record in result.drilldown:
        print "%s%s: count: %d amount: %d" % (indent, record[level_label], record["record_count"], record["amount_sum"])

        if not hierarchy.path_is_base(path):
            drill_path = path[:] + [record[level_key]]
            drill_down_cell = cell.slice(dimension, drill_path)
            drill_down(drill_down_cell, dimension, drill_path)

# Drill down through all levels of item hierarchy
browser = cubes.backends.sql.SQLBrowser(cube, connection, view_name = FACT_VIEW)

cell = browser.full_cube()

print "Drill down through all item levels:"
drill_down(cell, cube.dimension("item"))

print "Drill down through all item for year 2010:"
cell = cell.slice("year", [2010])
drill_down(cell, cube.dimension("item"))

