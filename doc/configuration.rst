+++++++++++++
Configuration
+++++++++++++


Cubes workspace configuration is stored in a ``.ini`` file with sections:

* ``[server]`` - server related configuration, such as host, port
* ``[workspace]`` – Cubes workspace configuration
* ``[model]`` - model and cube configuration
* ``[models]`` - list of models to be loaded (deprecated) 
* ``[store]`` – default datastore configuration
* ``[store NAME]`` – configuration for store with name `NAME`
* ``[locale NAME]`` - model translations. See :doc:`localization` for more
  information.
* ``[info]`` - optional section for user presentable info about your project

.. note::

    The configuration has changed with version 1.0. Since Cubes supports 
    multiple data stores, their type (backend) is specified in the store
    configuration as ``type`` property, for example ``type=sql``.

Quick Start
===========

Simple configuration might look like this:

.. code-block:: ini

    [workspace]
    model = model.json

    [store]
    type = sql
    url = postgresql://localhost/database

Server
======

``json_record_limit``
---------------------

Number of rows to limit when generating JSON output with iterable objects, such
as facts. Default is 1000. It is recommended to use alternate response format,
such as CSV, to get more records.

``modules``
-----------

Space separated list of modules to be loaded. This is only used if run by the 
:doc:`slicer command <slicer>`.

``prettyprint``
---------------

If set to ``true``, JSON is serialized with indentation of 4 spaces. Set to
``true`` for demonstration purposes, omit or comment out option for production
use.

``host``
--------

Host or IP address where the server binds, defaults to ``localhost``.

``port``
--------

Port on which the server listens, defaults to ``5000``.

``reload``
----------

Suitable for development only. Set to ``yes`` to enable 
`Werkzeug <http://werkzeug.pocoo.org/>`_ reloader.

``allow_cors_origin``
---------------------

Cross-origin resource sharing header. Other related headers are added as well,
if this option is present.

``authentication``
------------------

Authentication method, see `Authentication and Authorization`_ below for
more information.

``pid_file``
------------

Path to a file where PID of the running server will be written. If not 
provided, no PID file is created.


Workspace
=========

This section covers the Workspace configuration, such as file locations,
logging, namespaces and localization.

Authorization
-------------

``authorization``
~~~~~~~~~~~~~~~~~

Authorization method to be used on the workspace side. If omitted, no
authorization is required. For details see `Authentication and Authorization`_
below.

Localization configuration
--------------------------

``timezone``
~~~~~~~~~~~~

Name of the default time zone, for example ``Europe/Berlin``. Used in date and
time operations, such as :ref:`named relative time <named_relative_time>`.

``first_weekday``
~~~~~~~~~~~~~~~~~

First day of the week in english weekday name. Can also be specified as number,
where 0 is Monday and 6 is Sunday.


File Locations
--------------

``root_directory``
~~~~~~~~~~~~~~~~~~

Workspace root path: all paths, such as ``models_directory`` or ``info_file``
are considered relative to the ``root_directory`` it they are not specified as
absolute.

``models_directory``
~~~~~~~~~~~~~~~~~~~~

Path to a directory containing models. If this is set to non-empty value, then
all model paths specified in ``[models]`` are prefixed with this path.

``stores_file``
~~~~~~~~~~~~~~~

Path to a file (with `.ini` config syntax) containing store descriptions – 
every section is a store with same name as the section.

``info_file``
~~~~~~~~~~~~~

Path to a file containing user info metadata. See more in `Info`_.

Logging configuration
---------------------

``log``
~~~~~~~~

Path to log file.

``log_level``
~~~~~~~~~~~~~

Level of log details, from least to most: ``error``, ``warn``, ``info``,
``debug``.


Namespaces
----------

If not specified otherwise, all cubes share the same default namespace. Their
names within namespace should be unique.


Model
=====

``path``
--------

Path to model .json file. See :doc:`model` for more on model definition.

Models
======

.. warning::

    This section is deprecated in favor of section ``[model]``.

Section ``[models]`` contains list of models. The property names are model
identifiers within the configuration (see ``[translations]`` for example) and
the values are paths to model files.

Example:

.. code-block:: ini

    [models]
    main = model.json
    mixpanel = mixpanel.json

If `models_directory`_ is specified in `Workspace`_ then the relative
model paths are combined with the `models_directory`_. Example:

.. code-block:: ini

    [workspace]
    models_directory = /dwh/cubes/models

    [models]
    main = model.json
    events = events.json

The models are loaded from ``/dwh/cubes/models/model.json`` and
``/dwh/cubes/models/events.json``.

.. note::

    If the `root_directory`_ is set, then the ``models_directory`` is
    relative to the ``root_directory``. For example if the workspace root is
    ``/var/lib/cubes`` and ``models_directory`` is ``models`` then the search
    path for models will be ``/var/lib/cubes/models``. If the
    ``models_directory`` is absolute, for example ``/cubes/models`` then the
    absolute path will be used regardless of the workspace root directory
    settings.

Data stores
===========

There might be one or more store configured. The section ``[store]``
of the ``cubes.ini`` file describes the default store. Multiple stores are
configured in a separate ``stores.ini`` file referenced by the `stores_file`_ 
configuration option in ``[workspace]`` section.

Data store properties
---------------------

``type``
~~~~~~~~

Defines the data store backend module used, eg. ``sql``. Required.

For list of available types see :doc:`backends/index`.

``model``
~~~~~~~~~

Model related to the datastore.

``namespace``
~~~~~~~~~~~~~

Namespace where the store's cubes will be registered.

``model_provider``
~~~~~~~~~~~~~~~~~~

Model provider type for the datastore. For more on model providers, see
chapter :doc:`Model Provider and External Models <model>`.


Example data store configurations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example SQL store:

.. code-block:: ini

    [store]
    type = sql
    url = postgresql://localhost/data
    schema = cubes

For more information and configuration on SQL store options see :doc:`backends/sql`.

Example :doc:`mixpanel <backends/mixpanel>` store:

.. code-block:: ini

    [store]
    type = mixpanel
    model = mixpanel.json
    api_key = 123456abcd
    api_secret = 12345abcd

Multiple :doc:`Slicer <backends/slicer>` stores:

.. code-block:: ini

    [store slicer1]
    type = slicer
    url = http://some.host:5000

    [store slicer2]
    type = slicer
    url = http://other.host:5000

The cubes will be named `slicer1.*` and `slicer2.*`. To use specific
namespace, different from the store name:

.. code-block:: ini

    [store slicer3]
    type = slicer
    namespace = external
    url = http://some.host:5000

Cubes will be named `external.*`

To specify default namespace:

.. code-block:: ini

    [store slicer4]
    type = slicer
    namespace = default.
    url = http://some.host:5000

Cubes will be named without namespace prefix.

Authentication and Authorization
================================

Cubes provides mechanisms for authentication at the server side and
authorization at the workspace side.

Authorization
-------------

To configure authorization, you need to enable 
`authorization in workspace section <authorization>`_.

.. code-block:: ini

    [workspace]
    authorization = simple

    [authorization]
    rights_file = /path/to/access_rights.json

``authorization``
~~~~~~~~~~~~~~~~~

This option goes in the ``[workspace]`` section.

Valid options are 

* ``none`` – no authorization
* ``simple`` – uses a JSON file with per-user access rights

Simple authorization
--------------------

The simple authorization has following configuration options:

``rights_file``
~~~~~~~~~~~~~~~

Path to the JSON configuration file with access rights.

``roles_file``
~~~~~~~~~~~~~~

Path to the JSON configuration file with roles.

``identity_dimension``
~~~~~~~~~~~~~~~~~~~~~~

Name of a flat dimension that will be used for cell restriction. Key of that
dimension should match the identity.

``order``
~~~~~~~~~

Access control. Valid is ``allow_deny`` or ``deny_allow`` (default).

``guest``
~~~~~~~~~

Name of a guest role. If specified, then this role will be used
for all unknown (not specified in the file) roles.

Authentication
--------------

Example authentication via parameter passing:

.. code-block:: ini

    [server]
    authentication = pass_parameter

    [authentication]
    # additional authentication parameters
    parameter = token

This configures server to expect a GET parameter ``token`` which will be passed
on to authorization.

``authentication``
~~~~~~~~~~~~~~~~~~

Built-in server authentication methods:

``none``

    No authentication.

``http_basic_proxy``

    HTTP basic authentication will pass the `username` to the authorizer. This
    assumes the server is behind a proxy and that the proxy authenticated the
    user.

``pass_parameter``

    Authentication without verification, just a way of passing an URL parameter
    to the authorizer. Parameter name can be specified via ``parameter`` option,
    default ``api_key``.

For more on how this works, see :doc:`auth`.

.. note::

    When you have authorization method specified and is based on an users's
    indentity, then you have to specify the authentication method in the
    server. Otherwise the authorizer will not receive any identity and might
    refuse any access.


Localization sections
=====================

Model localizations are specified in the configuration with ``[locale XX]``
where ``XX`` is the two letter 
`ISO 639-1 locale code <http://en.wikipedia.org/wiki/List_of_ISO_639-1_codes>`_.
Option names are namespace names and option keys are paths to translation files.
For example:

.. code-block:: ini

    [locale sk]
    default = translation_sk.json

    [locale hu]
    default = translation_hu.json


Info
====

This section contains user supplied and front-end presentable information such
as description or license. This can be included in main .ini configuration or
as a separate JSON file.

The info JSON file might contain:

* ``label`` – server's name or label
* ``description`` – description of the served data
* ``copyright`` – copyright of the data, if any
* ``license`` – data license
* ``maintainer`` – name of the data maintainer, might be in format `Name
  Surname <namesurname@domain.org>`
* ``contributors`` - list of contributors
* ``keywords`` – list of keywords that describe the data
* ``related`` – list of related or "friendly" Slicer servers with other open
  data – a dictionary with keys ``label`` and ``url``.
* ``visualizers`` – list of links to prepared visualisations of the
  server's data – a dictionary with keys ``label`` and ``url``.


Server Query Logging
====================

Sections, prefixed with `query_log` configure query logging. All sections with
this prefix (including section named as the prefix) are collected and chained
into a list of logging handlers. Required option is `type`. You might have
multiple handlers at the same time.

Configuration options are:

``type``
--------

Type of query log. Required.

Valid options are:

``default``

    Log using Cubes logger via Python logging module.

``csv_file``

    Log into a CSV file. Specify the file name via ``path`` option.

``json``

    Log into file as quasi-JSON file - each log record is valid JSON and records
    are separated by newlines. Specify the file name via ``path`` option.


``sql``

    Log into a SQL table. SQL request logger options are:

    * `url` – database URL
    * `table` – database table
    * `dimensions_table` – table with dimension use (optional)

    If tables do not exist, they are created automatically.

Example query log configuration
-------------------------------

This configuration will create three query loggers, all at once. `query_log_one`
will emit to Python logging and will show in console if `log_level`_ is set to 
``info`` or more verbose. `query_log_two` will log queries into CSV file 
/var/log/cubes/queries.csv. `query_log_three` will insert query log into table 
`cubes_query_log` in a PostgreSQL database named `cubes_log` located on a remote
host named `log_host`.

.. code-block:: ini

    [query_log_one]
    type = default

    [query_log_two]
    type = csv
    path = /var/log/cubes/queries.csv

    [query_log_three]
    type = sql
    url = postgresql://log_host/cubes_log
    table = cubes_query_log


Examples
========


Simple configuration:

.. code-block:: ini

    [workspace]
    model = model.json

    [store]
    type = sql
    url = postgresql://localhost/cubes

Multiple models, one store:

.. code-block:: ini

    [models]
    finance = finance.cubesmodel
    customer = customer.cubesmodel

    [store]
    type = sql
    url = postgresql://localhost/cubes

Multiple stores:

.. code-block:: ini

    [store finance]
    type = sql
    url = postgresql://localhost/finance
    model = finance.cubesmodel

    [store customer]
    type = sql
    url = postgresql://otherhost/customer
    model = customer.cubesmodel


Example of a whole configuration file:

.. code-block:: ini

    [workspace]
    model = ~/models/contracts_model.json

    [server]
    log = /var/log/cubes.log
    log_level = info

    [store]
    type = sql
    url = postgresql://localhost/data
    schema = cubes
