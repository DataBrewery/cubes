Hello World! example for cubes
==============================

Files
-----

This directory contains following files:

    * model.json      - logical model
    * slicer.ini      - server configuration file
    * data.csv        - source data
    * prepare_data.py - script for preparing the data: load them into database
                        and create a view
    * aggregate.py    - example aggregations

Quick start
-----------

Prepare data::

    python2.7 prepare_data.py

Get some aggregations::

    python2.7 aggregate.py

Hello Server!
-------------

Run the server::

    slicer serve slicer.ini
    
Try the server. Aggregate::

  curl "http://localhost:5000/cube/irbd_balance/aggregate"
    
Aggregate by year::

  curl "http://localhost:5000/cube/irbd_balance/aggregate?drilldown=year"

Aggregate by category (top level for dimension item)::

  curl "http://localhost:5000/cube/irbd_balance/aggregate?drilldown=item" 

Aggregate by subcategory for item category 'e'::

  curl "http://localhost:5000/cube/irbd_balance/aggregate?drilldown=item&cut=item:e"

Note the implicit hierarchy of the `item` dimension.

See also the Slicer server documentation for more types of requests:
http://packages.python.org/cubes/server.html

Credits
-------

The example data used are IBRD Balance Sheet taken from The World Bank:

https://finances.worldbank.org/Accounting-and-Control/IBRD-Balance-Sheet-FY2010/e8yz-96c6

