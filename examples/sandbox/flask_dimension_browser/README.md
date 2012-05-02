Flask Dimension Browser
=======================

Simple browser of dimension hierarchy served with Flask web microframework.
The application displays an aggregated table where user can drill down through
dimension levels.

Requirements
------------

Install flask::

    pip install flask
    
You also need jinja2 which should be installed together with flask as its
dependency.

Flask home page: http://flask.pocoo.org/

Quick start
-----------

Prepare data::

    python prepare_data.py

Run the server::

    python application.py

And navigate your browser to http://127.0.0.1:5000/

Files
-----

This directory contains following files:

    * model.json      - logical model
    * data.csv        - source data
    * prepare_data.py - script for preparing the data: load them into database
                        and create a view
    * application.py  - the web application (see commends in the file)
    * templates/report.html - HTML template that shows the simple table report
                        (see comments in the file)
    * static/         - just static files, such as Twitter Bootstrap css so it can be pretty

Examples for the new StarBrowser are with suffix `*_star` (compare the report
templates with diff).
    
Credits
-------

The example data used are IBRD Balance Sheet taken from The World Bank:

https://finances.worldbank.org/Accounting-and-Control/IBRD-Balance-Sheet-FY2010/e8yz-96c6

