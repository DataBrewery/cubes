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
    

``/facts``
    Return all facts (details) within cuboid.

    :Parameters:
        * `cut` - see ``/aggregate``
        * `page`, `pagesize` - paginate results
        * `order` - order results
    
``/fact/<id>``
    Get single fact with specified `id`. For example: ``/fact/1024``
    
``/dimension/<dimension>``
    Get values for attributes of a `dimension`.
    
    :Parameters:
        * `depth` - specify depth (number of levels) to retrieve. If not specified, then all
          levels are returned
        * `cut` - see ``/aggregate``
        * `page`, `pagesize` - paginate results
        * `order` - order results
        
``/report``
    Process multiple request within one API call. (Not yet implemented)
    
``/drilldown/<dimension>/<path>``
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


Reports
-------

.. warning::

    Reports are neot yet implemented, this is preliminary proposal.

Report queries are done either by specifying a report name in the request URL or using HTTP POST
request where posted data are JSON with report specification. If report name is specified, then
server should have a repository of named report specifications.

Keys:

    * `datasets` - dictionary reported dataset specifications

Dataset specification:

    * `type` - query type: ``aggregate``, ``details`` (list of facts) or ``values`` for dimension values
    * `cut` - cut specification - a string same as the one used in URL request (might be a
      dictionary in the future)

Following example report query from a `contracts` cube will return three datasets (results):

    * total amount of contracts (aggregation "summary" - one record)
    * number of contracts and contracted amount for each year (aggregation drill down)
    * list of contractors and contracted amounts for contracts within IT segment

Report request::

    {
        "summary": { 
            "request": "aggregate" 
        },
        "year_drilldown" : { 
            "request": "aggregate", 
            "rollup": "date",
            "drilldown": "date"
        },
        "it_contractors" : { 
            "request": "aggregate",
            "drilldown": "contractor",
            "cut": { "subject": "it" }
        }
        
    }


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

Create server configuration ``procurements_server.json`` json file as in the example before::

    {
        "model": "/path/to/procurements_model.json",
        "cube": "contracts",
        "view": "mft_contracts",
        "connection": "postgres://localhost/procurements"
    }

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
