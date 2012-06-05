import sqlalchemy
import cubes
import cubes.tutorial.sql as tutorial

# In this tutorial you are going to learn how to start with cubes. The example shows:
# 
# how to build a model programatically
# how to create a model with flat dimensions
# how to aggregate whole cube
# how to drill-down and aggregate through a dimension
# The example data used are IBRD Balance Sheet taken from The World Bank
# Source: https://raw.github.com/Stiivi/cubes/master/tutorial/data/IBRD_Balance_Sheet__FY2010.csv
# 
# Create a tutorial directory and download the file:


# 1. Prepare SQL data in memory

engine = sqlalchemy.create_engine('sqlite:///:memory:')
tutorial.create_table_from_csv(engine,
                      "data/IBRD_Balance_Sheet__FY2010.csv",
                      table_name="irbd_balance",
                      fields=[
                            ("category", "string"),
                            ("line_item", "string"),
                            ("year", "integer"),
                            ("amount", "integer")],
                      create_id=True
                )

# 2. Create a model from a dictionary

model_description = {
    "dimensions": [
        { "name": "category"},
        { "name": "line_item"},
        { "name": "year"}
    ],
    "cubes": [
        {
            "name": "irbd_balance",
            "dimensions": ["category", "line_item", "year"],
            "measures": ["amount"]
        }
    ]
}

model = cubes.create_model(model_description)
cube = model.cube("irbd_balance")

# 4. Create a browser and get a cell representing the whole cube (all data)

workspace = cubes.create_workspace("sql.star", model, engine=engine)
browser = workspace.browser(cube)

cell = browser.full_cube()

# 5. Compute the aggregate
#    Measure fields of aggregation result have aggregation suffix, currenlty only _sum. Also
#    a total record count within the cell is included as record_count

result = browser.aggregate(cell)

print "Record count: %d" % result.summary["record_count"]
print "Total amount: %d" % result.summary["amount_sum"]

# 6. Drill-down through a dimension

print "Drill Down by Category"
result = browser.aggregate(cell, drilldown=["category"])

print "%-20s%10s%10s" % ("Category", "Count", "Total")
for record in result.drilldown:
    print "%-20s%10d%10d" % (record["category"], record["record_count"], record["amount_sum"])

print "Drill Down by Year:"
result = browser.aggregate(cell, drilldown=["year"])
print "%-20s%10s%10s" % ("Year", "Count", "Total")
for record in result.drilldown:
    print "%-20s%10d%10d" % (record["year"], record["record_count"], record["amount_sum"])
