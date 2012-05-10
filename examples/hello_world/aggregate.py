import sqlalchemy
import cubes

# 1. Prepare SQL data in memory
model = cubes.load_model("model.json")
workspace = cubes.create_workspace("sql.browser", model,
                                   url='sqlite:///data.sqlite',
                                   view_prefix='vft_')

# 2. Create a model
cube = model.cube("irbd_balance")

# 3. Create a browser and get a cell representing the whole cube (all data)
browser = workspace.browser(cube)
cell = browser.full_cube()

# 4. Play with aggregates
result = browser.aggregate(cell)

print "Total\n" \
      "----------------------"

print "Record count: %8d" % result.summary["record_count"]
print "Total amount: %8d" % result.summary["amount_sum"]

#
# The End!
#
# ... of the Hello World! example
#
# The following is more than just plain "hello"... uncomment it all to the end.
#
#
# 5. Drill-down through a dimension
#
# 
# print "\n" \
#       "Drill Down by Category (top-level Item hierarchy)\n" \
#       "================================================="
# 
# result = browser.aggregate(cell, drilldown=["item"])
# 
# print ("%-20s%10s%10s\n"+"-"*40) % ("Category", "Count", "Total")
# 
# for record in result.drilldown:
#     print "%-20s%10d%10d" % ( record["item.category_label"],
#                               record["record_count"],
#                               record["amount_sum"])
# 
# print "\n" \
#       "Slice where Category = Equity\n" \
#       "================================================="
# 
# cut = cubes.browser.PointCut("item", ["e"])
# cell = cubes.browser.Cell(browser.cube, cuts = [cut])
# 
# result = browser.aggregate(cell, drilldown=["item"])
# 
# print ("%-20s%10s%10s\n"+"-"*40) % ("Sub-category", "Count", "Total")
#       
# 
# for record in result.drilldown:
#     print "%-20s%10d%10d" % ( record["item.subcategory_label"],
#                               record["record_count"],
#                               record["amount_sum"])
