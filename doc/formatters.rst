***************
Data Formatters
***************

Data and metadata from aggregation result can be transformed to one of
multiple forms using formatters:

.. code-block:: python

    formatter = cubes.create_formatter("cross_table")

    result = browser.aggregate(cell, drilldown="date")

    print formatter.format(result, "date")  # This line doesn't work any more - what should it be?


Available formatters:

* `cross_table` – cross table structure with attributes `rows` – row headings,
  `columns` – column headings and `data` with rows of cells
* `csv` - comma-separated values
* `html_cross_table` – HTML version of the `cross_table` formatter

.. seealso::

    :doc:`reference/formatter`
        Formatter reference
