# -*- coding=utf  -*-
# Formatters example
#
# Requirements:
#       Go to the ../hello_world directory and do: python prepare_data.py
#
# Instructions:
#
#       Just run this file:
#
#            python table.py
# Output:
#   * standard input – text table
#   * table.html
#   * cross_table.html
#

from cubes import Workspace, create_formatter

workspace = Workspace("slicer.ini")

# Create formatters
text_formatter = create_formatter("text_table")
html_formatter = create_formatter("simple_html_table")
html_cross_formatter = create_formatter("html_cross_table")

# Get the browser and data

browser = workspace.browser("irbd_balance")

result = browser.aggregate(drilldown=["item"])
result = result.cached()

#
# 1. Create text output
#
print "Text output"
print "-----------"

print text_formatter(result, "item")


#
# 2. Create HTML output (see table.html)
#
with open("table.html", "w") as f:
    data = html_formatter(result, "item")
    f.write(data)

#
# 3. Create cross-table to cross_table.html
#
result = browser.aggregate(drilldown=["item", "year"])
with open("cross_table.html", "w") as f:
    data = html_cross_formatter(result,
                                onrows=["year"],
                                oncolumns=["item.category_label"])
    f.write(data)

print "Check also table.html and cross_table.html files"
