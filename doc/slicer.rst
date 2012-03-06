slicer - Command Line Tool
**************************

Cubes comes with a command line tool that can:

* run OLAP server
* build and compute cubes
* validate and translate models

Usage::

    slicer command [command_options]

or::
    
    slicer command sub_command [sub_command_options]

Commands are:

+-----------------------+----------------------------------------------------------------------+
| Command               | Description                                                          |
+=======================+======================================================================+
|``serve``              | Start OLAP server                                                    |
+-----------------------+----------------------------------------------------------------------+
|``model validate``     | Validates logical model for OLAP cubes                               |
+-----------------------+----------------------------------------------------------------------+
|``model json``         | Create JSON representation of a model (can be used)                  |
|                       | when model is a directory.                                           |
+-----------------------+----------------------------------------------------------------------+
|``build``              | Build OLAP cube from source data using model                         |
+-----------------------+----------------------------------------------------------------------+

serve
-----

Run Cubes OLAP HTTP server.

Example server configuration file ``slicer.ini``::

    [server]
    host: localhost
    port: 5000
    reload: yes
    log_level: info

    [db]
    url: sqlite:///tutorial.sqlite
    view_prefix: vft_

    [model]
    path: models/model_04.json
    
To run local server::

    slicer serve slicer.ini

In the ``[server]`` section, space separated list of modules to be imported can 
be specified under option ``modules``::

    [server]
    modules=cutom_backend
    ...

For more information about OLAP HTTP server see :doc:`/server`


model validate
--------------

Usage::

    slicer model validate /path/to/model/directory
    slicer model validate model.json
    slicer model validate http://somesite.com/model.json

For more information see Model Validation in :doc:`cubes`


Example output::

    loading model wdmmg_model.json
    -------------------------
    cubes: 1
        wdmmg
    dimensions: 5
        date
        pog
        region
        cofog
        from
    -------------------------
    found 3 issues
    validation results:
    warning: No hierarchies in dimension 'date', flat level 'year' will be used
    warning: Level 'year' in dimension 'date' has no key attribute specified
    warning: Level 'from' in dimension 'from' has no key attribute specified
    0 errors, 3 warnings

model json
----------

For any given input model produce reusable JSON model.

model extract_locale
--------------------

Extract localizable parts of the model. Use this before you start translating the model to get
translation template.

model translate
---------------

Translate model using translation file.
