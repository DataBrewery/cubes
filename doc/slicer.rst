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
|``extract_locale``     | Get localizable part of the model                                    |
+-----------------------+----------------------------------------------------------------------+
|``translate``          | Translate model with translation file                                |
+-----------------------+----------------------------------------------------------------------+
|``test``               | Test the model against backend database *(experimental)*             |
+-----------------------+----------------------------------------------------------------------+
|``ddl``                | Generate DDL for SQL backend *(experimental)*                        |
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

    [workspace]
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


Optional arguments::

      -d, --defaults        show defaults
      -w, --no-warnings     disable warnings
      -t TRANSLATION, --translation TRANSLATION
                            model translation file
                            
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

The tool output contains recommendation whether the model can be used:

* `model can be used` - if there are no errors, no warnings and no defaults used,
  mostly when the model is explicitly described in every detail
* `model can be used, make sure that defaults reflect reality` - there are no 
  errors, no warnings, but the model might be not complete and default 
  assumptions are applied
* `not recommended to use the model, some issues might emerge` - there are just 
  warnings, no validation errors. Some queries or any other operations might 
  produce invalid or unexpected output
* `model can not be used` - model contain errors and it is unusable


model json
----------

For any given input model produce reusable JSON model.

model extract_locale
--------------------

Extract localizable parts of the model. Use this before you start translating the model to get
translation template.

model translate
---------------

Translate model using translation file::

    slicer model translate model.json translation.json
ddl
---

.. note::

    This is experimental command.
    
Generates DDL schema of a model for SQL backend

Usage::

    slicer ddl [-h] [--dimension-prefix DIMENSION_PREFIX]
              [--fact-prefix FACT_PREFIX] [--backend BACKEND]
              url model

positional arguments::

    url                   SQL database connection URL
    model                 model reference - can be a local file path or URL

optional arguments::

    --dimension-prefix DIMENSION_PREFIX
                        prefix for dimension tables
    --fact-prefix FACT_PREFIX
                        prefix for fact tables
    --backend BACKEND     backend name (currently limited only to SQL backends)
