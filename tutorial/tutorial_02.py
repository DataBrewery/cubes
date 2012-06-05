import sqlalchemy
import cubes
import cubes.tutorial.sql as tutorial
import logging
import copy
        
# In this tutorial you are going to learn how to create a model file and use hierarchies. 
# The example shows:
# 
# * how to create and use a model file
# * mappings
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

# 2. Load model and get cube of our interest

model = cubes.load_model("models/model_02.json")
cube = model.cube("irbd_balance")

# 3. Create a browser

workspace = cubes.create_workspace("sql.star", model, engine=engine)
browser = workspace.browser(cube)

# 4. get a cell representing the whole cube (all data)

cell = browser.full_cube()
result = browser.aggregate(cell)

print "Record count: %d" % result.summary["record_count"]
print "Total amount: %d" % result.summary["amount_sum"]

print "Drill Down by Category - top level:"

result = browser.aggregate(cell, drilldown=["item"])

print "%-20s%10s%10s" % ("Category", "Count", "Total")
for record in result.drilldown:
    print "%-20s%10d%10d" % (record["item.category"], record["record_count"], record["amount_sum"])
