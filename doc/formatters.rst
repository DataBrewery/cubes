***************
Data Formatters
***************

Data and metadata from aggregation result can be transformed to one of
multiple forms using formatters:

.. code-block:: python
    formatter = cubes.create_formatter("text_table")

    result = browser.aggregate(cell, drilldown="date")

    print formatter.format(result, "date")

Output::

    FIXME: put output here

Available formmaters:

* `text_table` – text output for result of drilling down through one
  dimension
* `simple_data_table` – returns a dictionary with `header` and `rows`
* `simple_html_table` – returns a HTML table representation of result table
  cells

