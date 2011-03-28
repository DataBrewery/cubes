OLAP Web Service
++++++++++++++++


Cubes framework provides easy to install web service WSGI server with API that covers most of the
Cubes logical model metadata and aggregation browsing functionality.

Server requires the werkzeug_ framework.

.. _werkzeug: http://werkzeug.pocoo.org/

API
===

``GET /model``
    Get model metadata as JSON
    
``GET /model/dimension/<name>``
    Get dimension metadata as JSON

``GET /model/dimension/<name>/levels``
    Get list level metadata from default hierarchy of requested dimension.
    
.. _serveraggregate:

``GET /aggregate``
    Return aggregation result as JSON. The result will contain keys: `summary` and `drilldown`. The
    summary contains one row and represents aggregation of whole cuboid specified in the cut. The
    `drilldown` contains rows for each value of drilled-down dimension.
    
    If no arguments are given, then whole cube is aggregated.
    
    :Paramteres:
        * `cut` - specification of cuboid, for example:
          ``cut=date:2004,1|category=2|entity=12345``
        * `drilldown` - dimension to be drilled down. For example ``drilldown=date`` will give
          rows for each value of next level of dimension date.
        * `page` - page number for paginated results
        * `pagesize` - size of a page for paginated results
        * `order` - list of attributes to be ordered by
        * `limit` - limit number of results in form `limit`[,`measure`[,`order_direction`]]:
          ``limit=5:received_amount_sum:asc``

    Reply:
    
        * ``summary`` - dictionary of fields/values for summary aggregation
        * ``drilldown`` - list of drilled-down cells
        * ``remainder`` - summary of remaining cells (not in drilldown), if limit is specified.
          **Not implemented yet**
        * ``total_cell_count`` - number of total cells in drilldown (after `limir`, before pagination)

    If pagination is used, then ``drilldown`` will not contain more than ``pagesize`` cells.
    
    Note that not all backengs might implement ``total_cell_count`` or providing this information
    can be configurable therefore might be disabled (for example for performance reasons).
    

``GET /facts``
    Return all facts (details) within cuboid.

    :Parameters:
        * `cut` - see ``/aggregate``
        * `page`, `pagesize` - paginate results
        * `order` - order results
    
``GET /fact/<id>``
    Get single fact with specified `id`. For example: ``/fact/1024``
    
``GET /dimension/<dimension>``
    Get values for attributes of a `dimension`.
    
    :Parameters:
        * `depth` - specify depth (number of levels) to retrieve. If not specified, then all
          levels are returned
        * `cut` - see ``/aggregate``
        * `page`, `pagesize` - paginate results
        * `order` - order results
        
``POST /report``
    Process multiple request within one API call. The ``POST`` data should be a JSON containig
    report specification where keys are names of queries and values are dictionaries describing
    the queries.
    
    ``/report`` expects ``Content-type`` header to be set to ``application/json``.
    
    See :ref:`serverreport` for more information.
    
``GET /drilldown/<dimension>/<path>``
    Aggregate next level of dimension. This is similar to ``/aggregate`` with
    ``drilldown=<dimension>`` parameter. Does not result in error when path has largest possible
    length, returns empty results instead and result count 0. 
    
    If ``<path>`` is specified, it replaces any path specified in ``cut=`` parameter for given
    dimension. If ``<path>`` is not specified, it is taken from cut, where it should be
    represented as a point (not range nor set).
    
    
    In addition to ``/aggregate``
    result, folloing is returned:
    
    * ``is_leaf`` - Flag determining whether path refers to leaf or not. For example, this flag
      can be used to determine whether create links (is not last) or not (is last)
    * ``dimension`` - name of drilled dimension
    * ``path`` - path passed to drilldown

    In addition to this, each returned cell contains additional attributes:
    * ``_path`` - path to the cell - can be used for constructing further browsable links
    
    .. note::
    
        Not yet implemented
    
    
Parameters that can be used in any request:

    * `prettyprint` - if set to ``true`` formatting spaces are added to json output

Cuts in URLs
------------

The cuboid - part of the cube we are aggregating or we are interested in - is specified by cuts.
The cut in URL are given as single parameter ``cut`` which has following format:

Examples::

    date:2004
    date:2004,1
    date:2004,1|class=5
    date:2004,1,1|category:5,10,12|class:5

Dimension name is followed by colon ``:``, each dimension cut is separated by ``|``, and path for
dimension levels is separated by a comma ``,``. Or in more formal way, here is the BNF for the cut::

    <list>      ::= <cut> | <cut> '|' <list>
    <cut>       ::= <dimension> ':' <path>
    <dimension> ::= <identifier>
    <path>      ::= <value> | <value> ',' <path>

Why dimension names are not URL parameters? This prevents conflict from other possible frequent
URL parameters that might modify page content/API result, such as ``type``, ``form``, ``source``. 

Following image contains examples of cuts in URLs and how they change by browsing cube aggregates:

.. figure:: url_cutting.png

    Example of how cuts in URL work and how they should be used in application view templates.


.. _serverreport:

Reports
=======

Report queries are done either by specifying a report name in the request URL or using HTTP
``POST`` request where posted data are JSON with report specification. If report name is specified
in ``GET`` request instead, then server should have a repository of named report specifications.

Keys:

    * `queries` - dictionary of named queries

Query specification:

    * `query` - query type: ``aggregate``, ``details`` (list of facts), ``values`` for dimension
      values, ``facts`` or ``fact`` for multiple or single fact respectively

Note that you have to set content type to ``application/json``.

Result is a dictionary where keys are the query names specified in report specification and values
are result values from each query call.

Example: ``report.json``::

    {
        "summary": {
            "query": "aggregate"
        },
        "by_year": {
            "query": "aggregate",
            "drilldown": ["date"],
            "rollup": "date"
        }
    }

Request::

    curl -H "Content-Type: application/json" --data-binary "@report.json" \
        "http://localhost:5000/report?prettyprint=true&cut=date:2004"

Reply::

    {
        "by_year": {
            "total_cell_count": 6, 
            "drilldown": [
                {
                    "record_count": 4390, 
                    "requested_amount_sum": 2394804837.56, 
                    "received_amount_sum": 399136450.0, 
                    "date.year": "2004"
                }, 
                ...
                {
                    "record_count": 265, 
                    "requested_amount_sum": 17963333.75, 
                    "received_amount_sum": 6901530.0, 
                    "date.year": "2010"
                }
            ], 
            "remainder": {}, 
            "summary": {
                "record_count": 33038, 
                "requested_amount_sum": 2412768171.31, 
                "received_amount_sum": 2166280591.0
            }
        }, 
        "summary": {
            "total_cell_count": null, 
            "drilldown": {}, 
            "remainder": {}, 
            "summary": {
                "date.year": "2004", 
                "requested_amount_sum": 2394804837.56, 
                "received_amount_sum": 399136450.0, 
                "record_count": 4390
            }
        }
    }


Roll-up
-------

Report queries might contain ``rollup`` specification which will result in "rolling-up"
one or more dimensions to desired level. This functionality is provided for cases when you
would like to report at higher level of aggregation than the cell you provided is in.
It works in similar way as drill down in :ref:`serveraggregate` but in
the opposite direction (it is like ``cd ..`` in a UNIX shell).

Example: You are reporting for year 2010, but you want to have a bar chart with all years.
You specify rollup::

    ...
    "rollup": "date",
    ...

Roll-up can be:

    * a string - single dimension to be rolled up one level
    * an array - list of dimension names to be rolled-up one level
    * a dictionary where keys are dimension names and values are levels to be rolled up-to

Running and Deployment
======================

Local Server
------------

To run your local server, prepare server configuration ``grants_config.json``::

    {
        "model": "grants_model.json",
        "cube": "grants",
        "view": "mft_grants",
        "connection": "postgres://localhost/mydata"
    }

Run the server using the Slicer tool (see :doc:`/slicer`)::

    slicer serve grants_config.json

Apache mod_wsgi deployment
--------------------------

Deploying Cubes OLAP Web service server (for analytical API) can be done in four very simple
steps:

1. Create server configuration json file
2. Create WSGI script
3. Prepare apache site configuration
4. Reload apache configuration

Create server configuration file ``server.ini``::

    [server]
    host: localhost
    port: 5001
    reload: yes

    [model]
    path: /path/to/model.json
    cube: procurements
    view: mft_procurements
    schema: datamarts
    connection: postgres://localhost/transparency

Place the file in the same directory as the following WSGI script (for convenience).

Create a WSGI script ``/var/www/wsgi/olap/procurements.wsgi``:

.. code-block:: python

    import sys
    import os.path
    import json

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_PATH = os.path.join(CURRENT_DIR, "procurements_server.json")

    handle = open(CONFIG_PATH)
    try:
        config = json.load(handle)
    except Exception as e:
        raise Exception("Unable to load configuration: %s" % e)
    finally:
        handle.close()

    import cubes.server
    application = cubes.server.Slicer(config)

Apache site configuration (for example in ``/etc/apache2/sites-enabled/``)::

    <VirtualHost *:80>
        ServerName olap.democracyfarm.org

        WSGIScriptAlias /vvo /var/www/wsgi/olap/procurements.wsgi

        <Directory /var/www/wsgi/olap>
            WSGIProcessGroup olap
            WSGIApplicationGroup %{GLOBAL}
            Order deny,allow
            Allow from all
        </Directory>

        ErrorLog /var/log/apache2/olap.democracyfarm.org.error.log
        CustomLog /var/log/apache2/olap.democracyfarm.org.log combined

    </VirtualHost>

Reload apache configuration::

    sudo /etc/init.d/apache2 reload

And you are done. Server is running at http://olap.democracyfarm.org/vvo

Server requests
---------------

Example server request to get aggregate for whole cube::

    $ curl http://localhost:5000/aggregate?cut=date:2004
    
Reply::

    {
        "drilldown": {}, 
        "remainder": {}, 
        "summary": {
            "date.year": "2004", 
            "received_amount_sum": 399136450.0, 
            "requested_amount_sum": 2394804837.56, 
            "record_count": 4390
        }
    }
