Cubes Tutorial 1 - Getting started
==================================

In this tutorial you are going to learn how to start with cubes. The example shows:

* how to build a model programatically
* how to create a model with flat dimensions
* how to aggregate whole cube
* how to drill-down and aggregate through a dimension

The example data used are [IBRD Balance Sheet](https://raw.github.com/Stiivi/cubes/master/tutorial/data/IBRD_Balance_Sheet__FY2010.csv) taken from [The World Bank](https://finances.worldbank.org/Accounting-and-Control/IBRD-Balance-Sheet-FY2010/e8yz-96c6)

Create a tutorial directory and download the file:

<pre>
curl -O https://raw.github.com/Stiivi/cubes/master/tutorial/data/IBRD_Balance_Sheet__FY2010.csv
</pre>

Create a ``tutorial_01.py``:

<pre class="prettyprint">
import sqlalchemy
import cubes
import cubes.tutorial.sql as tutorial
</pre>

Cubes package contains tutorial helper methods. It is advised not to use them in production, they are provided just to simplify learner's life.

Prepare the data using the tutorial helper methods:

<pre class="prettyprint">

engine = sqlalchemy.create_engine('sqlite:///:memory:')
tutorial.create_table_from_csv(engine, 
                      "IBRD_Balance_Sheet__FY2010.csv", 
                      table_name="irbd_balance", 
                      fields=[
                            ("category", "string"), 
                            ("line_item", "string"),
                            ("year", "integer"), 
                            ("amount", "integer")],
                      create_id=True    
                        
                        )
</pre>

Now, create a model:

<pre class="prettyprint">
model = cubes.Model()
</pre>

Add dimensions to the model. Reason for having dimensions in a model is, that they might be shared by multiple cubes.

<pre class="prettyprint">
model.add_dimension(cubes.Dimension("category"))
model.add_dimension(cubes.Dimension("line_item"))
model.add_dimension(cubes.Dimension("year"))
</pre>

Define a cube and specify already defined dimensions:
<pre class="prettyprint">
cube = cubes.Cube(name="irbd_balance", 
                  model=model,
                  dimensions=["category", "line_item", "year"],
                  measures=["amount"]
                  )
</pre>

Create a browser and get a cell representing the whole cube (all data):

<pre class="prettyprint">
browser = cubes.backends.sql.SQLBrowser(cube, engine.connect(), view_name = "irbd_balance")

cell = browser.full_cube()
</pre>

Compute the aggregate. Measure fields of aggregation result have aggregation suffix, currenlty only ``_sum``. Also a total record count within the cell is included as ``record_count``.


<pre class="prettyprint">
result = browser.aggregate(cell)

print "Record count: %d" % result.summary["record_count"]
print "Total amount: %d" % result.summary["amount_sum"]
</pre>

Now try some drill-down by category:

<pre class="prettyprint">
print "Drill Down by Category"
result = browser.aggregate(cell, drilldown=["category"])

print "%-20s%10s%10s" % ("Category", "Count", "Total")
for record in result.drilldown:
    print "%-20s%10d%10d" % (record["category"], record["record_count"], record["amount_sum"])
</pre>

Drill-dow by year:

<pre class="prettyprint">
print "Drill Down by Year:"
result = browser.aggregate(cell, drilldown=["year"])
print "%-20s%10s%10s" % ("Year", "Count", "Total")
for record in result.drilldown:
    print "%-20s%10d%10d" % (record["year"], record["record_count"], record["amount_sum"])
</pre>

All tutorials with example data and models will be stored together with [cubes sources](https://github.com/Stiivi/cubes) under the ``tutorial/`` directory.

Next: Model files and hierarchies.

If you have any questions, comments or suggestions, do not hesitate to ask.