********************
Analytical Workspace
********************

Analytical workspace is ... TODO: describe.

The analyital workspace manages cubes, shared (public) dimensions, data
stores, model providers and model metadata. Provides aggregation browsers and
maintains database connections.

.. figure:: images/cubes-analytical-workspace-overview.png
    :align: center
    :width: 500px

    Analytical Workspace

Typical cubes session takes place in a workspace. Workspace is configured
either through a ``slicer.ini`` file or programatically. Using the file:

.. code-block:: python

    from cubes import Workspace

    workspace = Workspace(config="slicer.ini")

For more information about the configuration file options see
:doc:`configuration`

The manual workspace creation:

.. code-block:: python

    from cubes import Workspace

    workspace = Workspace()
    workspace.register_default_store("sql", url="postgresql://localhost/data")
    workspace.import_model("model.json")

Stores
======

Cube data are stored somewhere or might be provided by a service. We call this
data source a data `store`. A workspace might use multiple stores to get
content of the cubes.

Built-in stores are:

* ``sql`` – relational database store (`ROLAP`_) using star or snowflake
  schema
* ``slicer`` – connection to another Cubes server
* ``mixpanel`` – retrieves data from `Mixpanel`_ and makes it look like
  multidimensional cubes

Supported SQL dialects (by SQLAlchemy) are: Drizzle, Firebird, Informix,
Microsoft SQL Server, MySQL, Oracle, PostgreSQL, SQLite, Sybase

.. _Mixpanel: https://mixpanel.com/docs/
.. _ROLAP: http://en.wikipedia.org/wiki/ROLAP

See :doc:`configuration` for more information how to configure the stores.


Model Providers
===============

Model provider creates models of cubes, dimensions and other analytical
objects. The models can be created from a metadata, database or an external
source, such as API.

Built-in model providers are:

* ``static`` (also aliased as ``default``) – creates model objects from JSON
  data (files)
* ``mixpanel`` – describes cubes as Mixpanel events and dimensions as Mixpanel
  properties


To specify that the model is provided from other source than the metadata use
the ``provider`` keyword in the model description:

.. code-block:: javascript

    {
        "provider": "mixpanel",
        "store": "mixpanel"
    }

The store::

    [store]
    type: mixpanel
    api_key: MY_MIXPANEL_API_KEY
    api_secret: MY_MIXPANEL_API_SECRET


