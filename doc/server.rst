OLAP Web Service
++++++++++++++++


Cubes framework provides easy to install web service WSGI server with API that covers most of the
Cubes logical model metadata and aggregation browsing functionality.

Server requires the werkzeug_ framework.

API
---

.. _werkzeug: http://werkzeug.pocoo.org/

``/model``
    Get model metadata as JSON
    
``/model/dimension/<name>``
    Get dimension metadata as JSON

``/model/dimension/<name>/levels``
    Get list level metadata from default hierarchy of requested dimension.
    
``/aggregate``
    Return aggregation result as JSON. The result will contain keys: `summary` and `drilldown`. The
    summary contains one row and represents aggregation of whole cuboid specified in the cut. The
    `drilldown` contains rows for each value of drilled-down dimension.
    
    If no arguments are given, then whole cube is aggregated.
    
    Possible arguments:
    
    * `cut` - specification of cuboid, for example: ``cut=date:2004,1|category=2|entity=12345``
    * `drilldown` - dimension to be drilled down. For example ``drilldown=date`` will give rows for
      each value of next level of dimension date.
    * `page` - page number for paginated results
    * `pagesize` - size of a page for paginated results
    * `order` - list of attributes to be ordered by
    * `limit` - limit number of results in form `limit`[,`measure`[,`order_direction`]]:
      ``limit=5:received_amount_sum:asc``
      
``/report``
    Process ultiple aggregate request within one API call.
    
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


Reports
-------

.. warning::

    Reports are neot yet implemented, this is preliminary proposal.

Report queries are done either by specifying a report name in the request URL or using HTTP POST
request where posted data are JSON with report specification. If report name is specified, then
server should have a repository of report specifications.

Keys:
* `datasets` - dictionary reported dataset specifications

Dataset specification:
* `type` - query type: ``aggregate``, ``details`` (list of facts) or ``values`` for dimension values
* `cut` - cut specification - a string similar to URL request (might be a dictionary in the future)


Simple example server
---------------------

Here is example of simple OLAP Cubes server. The server shown in the example is serving data from
a SQL database.

Import basics and configure paths, notably path to the logical model description. Let us assume
that the model is stored in the same directory as the server script:

.. code-block:: python

    #!/usr/bin/env python
    from werkzeug import script
    import os.path

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    MODEL_PATH = os.path.join(CURRENT_DIR, "model.json")

Prepare server configuration:

.. code-block:: python

    config = {
        "model": MODEL_PATH,

        # Name of served cube
        "cube": "grants",

        # Name of materialized denomralized view/table containing the cube data
        "view": "mft_grants",
        
        # SQL Alchemy Database URL
        "connection": "postgres://localhost/mydata"
    }

Functions to create and run the server:

.. code-block:: python

    def make_app():
        import cubes.server
        app = cubes.server.Slicer(config)
        return app

    def make_shell():
        from slicer import utils
        application = make_app()
        return locals()

    action_runserver = script.make_runserver(make_app, use_reloader=True)
    action_shell = script.make_shell(make_shell)

    script.run()

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
