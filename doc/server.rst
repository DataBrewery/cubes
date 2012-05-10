+++++++++++
OLAP Server
+++++++++++


Cubes framework provides easy to install web service WSGI server with API that 
covers most of the Cubes logical model metadata and aggregation browsing 
functionality.

.. note::

    Server requires the Werkzeug_ framework.

.. _Werkzeug: http://werkzeug.pocoo.org/

For more information about how to run the server programatically, please refer 
to the :mod:`server` module.

HTTP API
========

Model
-----

``GET /model``
    Get model metadata as JSON. In addition to standard model attributes a 
    ``locales`` key is added with list of available model locales.
    
``GET /model/dimension/<name>``
    Get dimension metadata as JSON

``GET /model/dimension/<name>/levels``
    Get list level metadata from default hierarchy of requested dimension.

``GET /locales``
    Get list of model locales

Cube
----

Cube API calls have format: ``/cube/<cube_name>/<browser_action>`` where the 
browser action might be ``aggregate``, ``facts``, ``fact``, ``dimension`` and 
``report``.

.. _serveraggregate:

``GET /cube/<cube>/aggregate``
    Return aggregation result as JSON. The result will contain keys: `summary` 
    and `drilldown`. The summary contains one row and represents aggregation of 
    whole cuboid specified in the cut. The `drilldown` contains rows for each 
    value of drilled-down dimension.
    
    If no arguments are given, then whole cube is aggregated.
    
    :Paramteres:
        * `cut` - specification of cuboid, for example:
          ``cut=date:2004,1|category=2|entity=12345``
        * `drilldown` - dimension to be drilled down. For example 
          ``drilldown=date`` will give rows for each value of next level of 
          dimension date. You can explicitly specify level to drill down in 
          form: ``dimension:level``, such as: ``drilldown=date:month``
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
    

``GET /cube/<cube>/facts``
    Return all facts (details) within cuboid.

    :Parameters:
        * `cut` - see ``/aggregate``
        * `page`, `pagesize` - paginate results
        * `order` - order results
        * `format` - result format: ``json`` (default; see note below), ``csv``
        * `fields` - comma separated list of fact fields, by default all fields are returned
    
    .. note::

        Number of facts in JSON is limited to configuration value of ``json_record_limit``, which is
        1000 by default. To get more records, either use pages with size less than record limit or
        use alternate result format, such as ``csv``.
    
``GET /cube/<cube>/fact/<id>``
    Get single fact with specified `id`. For example: ``/fact/1024``
    
``GET /cube/<cube>/dimension/<dimension>``
    Get values for attributes of a `dimension`.
    
    :Parameters:
        * `depth` - specify depth (number of levels) to retrieve. If not specified, then all
          levels are returned
        * `cut` - see ``/aggregate``
        * `page`, `pagesize` - paginate results
        * `order` - order results
        
``POST /cube/<cube>/report``
    Process multiple request within one API call. The ``POST`` data should be a JSON containig
    report specification where keys are names of queries and values are dictionaries describing
    the queries.
    
    ``report`` expects ``Content-type`` header to be set to ``application/json``.
    
    See :ref:`serverreport` for more information.
    
``GET /cube/<cube>/search/dimension/<dimension>/<query>``
    Search values of `dimensions` for `query`. If `dimension` is ``_all`` then all
    dimensions are searched. Returns search results as list of dictionaries with attributes:
    
    :Search result:
        * `dimension` - dimension name
        * `level` - level name
        * `depth` - level depth
        * `level_key` - value of key attribute for level
        * `attribute` - dimension attribute name where searched value was found
        * `value` - value of dimension attribute that matches search query
        * `path` - dimension hierarchy path to the found value
        * `level_label` - label for dimension level (value of label_attribute for level)
        
        
    .. warning::
    
        Not yet fully implemented, just proposal.
        

``GET /cube/<cube>/drilldown/<dimension>/<path>``
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
        "http://localhost:5000/cube/contracts/report?prettyprint=true&cut=date:2004"

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

To run your local server, prepare server configuration ``grants_config.ini``::

    [server]
    host: localhost
    port: 5000
    reload: yes
    log_level: info

    [workspace]
    url: postgres://localhost/mydata"

    [model]
    path: grants_model.json


Run the server using the Slicer tool (see :doc:`/slicer`)::

    slicer serve grants_config.ini

Apache mod_wsgi deployment
--------------------------

Deploying Cubes OLAP Web service server (for analytical API) can be done in four very simple
steps:

1. Create server configuration json file
2. Create WSGI script
3. Prepare apache site configuration
4. Reload apache configuration

Create server configuration file ``procurements.ini``::

    [model]
    path: /path/to/model.json

    [workspace]
    view_prefix: mft_
    schema: datamarts
    url: postgres://localhost/transparency

    [translations]
    en: /path/to/model-en.json
    hu: /path/to/model-hu.json


Place the file in the same directory as the following WSGI script (for convenience).

Create a WSGI script ``/var/www/wsgi/olap/procurements.wsgi``:

.. code-block:: python

    import sys
    import os.path
    import ConfigParser

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    CONFIG_PATH = os.path.join(CURRENT_DIR, "procurements.ini")

    try:
        config = ConfigParser.SafeConfigParser()
        config.read(CONFIG_PATH)
    except Exception as e:
        raise Exception("Unable to load configuration: %s" % e)

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

And you are done.

Server requests
---------------

Example server request to get aggregate for whole cube::

    $ curl http://localhost:5000/cube/procurements/aggregate?cut=date:2004
    
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

Configuration
-------------

Server configuration is stored in .ini files with sections:

* ``[server]`` - server related configuration, such as host, port
    * ``host`` - host where the server runs, defaults to ``localhost``
    * ``port`` - port on which the server listens, defaults to ``5000``
    * ``log`` - path to a log file
    * ``log_level`` - level of log details, from least to most: ``error``, 
      ``warn``, ``info``, ``debug``
    * ``json_record_limit`` - number of rows to limit when generating JSON 
      output with iterable objects, such as facts. Default is 1000. It is 
      recommended to use alternate response format, such as CSV, to get more 
      records.
    * ``modules`` - space separated list of modules to be loaded (only used if 
      run by the ``slicer`` command)
    * ``prettyprint`` - default value of ``prettyprint`` parameter. Set to 
      ``true`` for demonstration purposes.
* ``[model]`` - model and cube configuration
    * ``path`` - path to model .json file
    * ``locales`` - comma separated list of locales the model is provided in. 
      Currently this variable is optional and it is used only by experimental 
      sphinx search backend.
* ``[translations]`` - model translation files, option keys in this section are 
  locale names and values are paths to model translation files. See 
  :doc:`localization` for more information.


Backend workspace configuration should be in the ``[workspace]``. See
:doc:`/api/backends` for more information.

* ``[workspace]`` - relational database configuration (default SQL backend)
    * ``url`` - database URL in form: 
      ``adapter://user:password@host:port/database``
    * ``schema`` - schema containing denormalized views for relational DB cubes
    * ``view_prefix``, ``view_suffix`` - prefix and suffix for view or table 
      containing cube facts, name is constructed by concatenating `prefix` + 
      `cube name` + `suffix`

.. note::

    For backward compatibility, sections ``[backend]`` and ``[db]`` are also
    supported, but you should change them to ``[workspace]`` as soon as
    possible

Example configuration file::

    [server]
    host: localhost
    port: 5001
    reload: yes
    log: /var/log/cubes.log
    log_level: info

    [workspace]
    url: postgresql://localhost/data
    view: contracts
    schema: cubes

    [model]
    path: ~/models/contracts_model.json
    cube: contracts
    locales: en,sk

    [translations]
    sk: ~/models/contracts_model-sk.json
