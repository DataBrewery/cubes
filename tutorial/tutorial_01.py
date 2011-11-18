import sqlalchemy
import cubes
import cubes.tutorial.sql as tutorial
        
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

# 2. Create a model

model = cubes.Model()

# 3. Add dimensions to the model. Reason for having dimensions in a model is, that they
#    might be shared by multiple cubes.

model.add_dimension(cubes.Dimension("category"))
model.add_dimension(cubes.Dimension("line_item"))
model.add_dimension(cubes.Dimension("year"))

# 3. Define a cube and specify already defined dimensions

cube = cubes.Cube(name="irbd_balance", 
                  model=model,
                  dimensions=["category", "line_item", "year"],
                  measures=["amount"]
                  )

# 4. Create a browser and get a cell representing the whole cube (all data)

browser = cubes.backends.sql.SQLBrowser(cube, engine.connect(), view_name = "irbd_balance")

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

import json

print json.dumps(model.to_dict())
