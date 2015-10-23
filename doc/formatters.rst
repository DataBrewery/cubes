***************
Data Formatters
***************

Data and metadata from aggregation result can be transformed to one of
multiple forms using formatters:

.. code-block:: python

    formatter = cubes.create_formatter("text_table")

    result = browser.aggregate(cell, drilldown="date")

    print formatter.format(result, "date")


Available formatters:

* `text_table` – text output for result of drilling down through one
  dimension
* `simple_data_table` – returns a dictionary with `header` and `rows`
* `simple_html_table` – returns a HTML table representation of result table
  cells
* `cross_table` – cross table structure with attributes `rows` – row headings,
  `columns` – column headings and `data` with rows of cells
* `html_cross_table` – HTML version of the `cross_table` formatter

.. seealso::

    :doc:`reference/formatter`
        Formatter reference
