+++++++++++++
Configuration
+++++++++++++


Cubes workspace configuration is stored in a ``.ini`` file with sections:

* ``[workspace]`` – Cubes workspace configuration
* ``[server]`` - server related configuration, such as host, port
* ``[models]`` - list of models to be loaded 
* ``[datastore]`` – default datastore configuration
* ``[translations]`` - model translation files, option keys in this section
  are locale names and values are paths to model translation files. See
  :doc:`localization` for more information.
* ``[model]`` (depreciated) - model and cube configuration

.. note::

    The configuration has changed. Since Cubes supports multiple data stores,
    their type (backend) is specifien in the datastore configuration as
    ``type`` property, for example ``type=sql``.

Quick Start
===========

Simple configuration might look like this::

    [workspace]
    model: model.json

    [datastore]
    type: sql
    url: postgresql://localhost/database

Workspace
=========

* ``stores`` – path to a file containing store descriptions – every section is
  a store with same name as the section
* ``models_path`` – path to a directory containing models. If this is set to
  non-empty value, then all model paths specified in ``[models]`` are prefixed
  with this path
* ``log`` - path to a log file
* ``log_level`` - level of log details, from least to most: ``error``, 
    ``warn``, ``info``, ``debug``

* ``authorization`` – authorization method to be used

Models
======

Section ``[models]`` contains list of models. The property names are model
identifiers within the configuration (see ``[translations]`` for example) and
the values are paths to model files.

Example::

    [models]
    main: model.json
    mixpanel: mixpanel.json

If root ``models_path`` is specified in ``[workspace]`` then the relative
model paths are combined with the root. Example::

    [workspace]
    models_path: /dwh/cubes/models

    [models]
    main: model.json
    events: events.json

The models are loaded from ``/dwh/cubes/models/model.json`` and
``/dwh/cubes/models/events.json``.


Server
======

* ``json_record_limit`` - number of rows to limit when generating JSON 
    output with iterable objects, such as facts. Default is 1000. It is 
    recommended to use alternate response format, such as CSV, to get more 
    records.
* ``modules`` - space separated list of modules to be loaded (only used if 
    run by the ``slicer`` command)
* ``prettyprint`` - default value of ``prettyprint`` parameter. Set to 
    ``true`` for demonstration purposes.
* ``host`` - host where the server runs, defaults to ``localhost``
* ``port`` - port on which the server listens, defaults to ``5000``

* ``authentication`` – authentication method (see below for more information)

Model
=====

.. note::

    This section is depreciated. Use `model` in ``[workspace]`` for single
    model file or ``[models]`` for multiple models.

* ``path`` - path to model .json file
* ``locales`` - comma separated list of locales the model is provided in. 
    Currently this variable is optional and it is used only by experimental 
    sphinx search backend.

Data stores
===========

There might be one or more datastores configured. The section ``[datastore]``
of the ``cubes.ini`` file describes the default store. Multiple stores are
configured in a separate ``stores.ini`` file. The path to the stores
configuration file might be specified in a variable ``stores`` of the
``[workspace]`` section

The store configuration has to have at least one property: ``type``. Rest of
the properties are handled by the actual data store.

SQL store
---------

Example SQL store::

    [datastore]
    type: sql
    url: postgresql://localhost/data
    schema: cubes

For more information and configuration options see :doc:`backends/sql`.


Example
=======

Example configuration file::

    [workspace]
    model: ~/models/contracts_model.json

    [server]
    reload: yes
    log: /var/log/cubes.log
    log_level: info

    [datastore]
    type: sql
    url: postgresql://localhost/data
    schema: cubes

Authentication and Authorization
================================

Cubes provides mechanisms for authentication at the server side and
authorization at the workspace side.

Configure authorization:

.. code-block:: ini

    [workspace]
    authorization: simple

    [authorization]
    rights_file: /path/to/access_rights.json

Built-in authorization methods:

* ``none`` – no authorization
* ``simple`` – uses a JSON file with per-user access rights

Configure authentication:

.. code-block:: ini

    [server]
    authentication: parameter

    [authentication]
    # additional authentication parameters

Built-in server authentication methods:

* ``none`` – no authentication
* ``http_basic_proxy`` – HTTP basic authentication. Will pass the `username`
  to the authorizer
* ``pass_parameter`` – authentication withot verification, just a way of
  passing an URL parameter to the authorizer. Default parameter name is
  ``api_key``

.. note::

    When you have authorization method specified and is based on an users's
    indentity, then you have to specify the authentication method in the
    server. Otherwise the authorizer will not receive any identity and might
    refuse any access.
