Flask Dimension Browser
=======================

Simple browser of dimension hierarchy served with Flask web microframework.
The application displays an aggregated table where user can drill down through
dimension levels.

Requirements
------------

Prepare the `hello_world` data in ``../hello_world`` by running:

    python prepare_data.py

Use
---

Run the server::

    python application.py

And navigate your browser to http://localhost:5000/

You can also access the raw data using the Slicer at
http://localhost:5000/slicer

Files
-----

This directory contains following files:

    * application.py  - the web application (see commends in the file)
    * templates/report.html - HTML template that shows the simple table report
                        (see comments in the file)
    * static/         - just static files, such as Twitter Bootstrap css so it can be pretty

Credits
-------

The example data used are IBRD Balance Sheet taken from The World Bank:

https://finances.worldbank.org/Accounting-and-Control/IBRD-Balance-Sheet-FY2010/e8yz-96c6

