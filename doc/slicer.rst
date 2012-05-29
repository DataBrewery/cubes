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

denormalize
-----------

Usage::

    slicer denormalize [-h] [-p PREFIX] [-f] [-m] [-i] [-s SCHEMA]
                       [-c CUBE] config

positional arguments::

    config                slicer confuguration .ini file

optional arguments::

    -h, --help            show this help message and exit
    -p PREFIX, --prefix PREFIX
                          prefix for denormalized views (overrides config value)
    -f, --force           replace existing views
    -m, --materialize     create materialized view (table)
    -i, --index           create index for key attributes
    -s SCHEMA, --schema SCHEMA
                          target view schema (overrides config value)
    -c CUBE, --cube CUBE  cube(s) to be denormalized, if not specified then all
                        in the model

Examples
~~~~~~~~

If you plan to use denormalized views, you have to specify it in the
configuration in the ``[workspace]`` section::

    [workspace]
    denormalized_view_prefix = mft_
    denormalized_view_schema = denorm_views

    # This switch is used by the browser:
    use_denormalization = yes

The denormalization will create tables like ``denorm_views.mft_contracts`` for
a cube named ``contracts``. The browser will use the view if option
``use_denormalization`` is set to a true value.

Denormalize all cubes in the model::

    slicer denormalize slicer.ini
    
Denormalize only one cube::

    slicer denormalize -c contracts slicer.ini
    
Create materialized denormalized view with indexes::

    slicer denormalize --materialize --index slicer.ini

Replace existing denormalized view of a cube::

    slicer denormalize --force -c contracts slicer.ini

Schema
~~~~~~

Schema where denormalized view is created is schema specified in the
configuration file. Schema is shared with fact tables and views. If you want
to have views in separate schema, specify ``denormalized_view_schema`` option
in the configuration.

If for any specific reason you would like to denormalize into a completely
different schema than specified in the configuration, you can specify it with
the ``--schema`` option.

View name
~~~~~~~~~

By default, a view name is the same as corresponding cube name. If there is
``denormalized_view_prefix`` option in the configuration, then the prefix is
prepended to the cube name. Or it is possible to override the option with
command line argument ``--prefix``.

.. note::

    The tool will not allow to create view if it's name is the same as fact
    table name and is in the same schema. It is not even possible to
    ``--force`` it. A view prefix or different schema has to be specified.
