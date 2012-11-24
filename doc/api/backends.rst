*************************************************
:mod:`backends` --- Aggregation Browsing Backends
*************************************************

.. module:: backends
   :synopsis: backends for browsing aggregates of various data sources

SQL - Star
==========

Workspace
---------

.. autofunction:: cubes.backends.sql.workspace.create_workspace
.. autoclass:: cubes.backends.sql.workspace.SQLStarWorkspace

Browser
-------

.. autoclass:: cubes.backends.sql.star.SnowflakeBrowser
.. autoclass:: cubes.backends.sql.star.QueryContext


Helper functions
----------------

.. autofunction:: cubes.backends.sql.star.paginated_statement
.. autofunction:: cubes.backends.sql.star.ordered_statement
.. autofunction:: cubes.backends.sql.star.order_column


Slicer
======

This backend is just for backend development demonstration purposes.

.. autoclass:: cubes.backends.slicer.SlicerBrowser

Implementing Custom Backend
===========================

Custom backend is just a subclass of :class:`cubes.AggregationBrowser` class.

Slicer and Server Integration
-----------------------------

If the backend is intended to be used by the Slicer server, then backend should 
be placed in its own module. The module should contain a method 
`create_workspace(model, config)` which returns a workspace object. `config` is 
a configuration dictionary taken from the config file (see below). The 
workspace object should implement `browser_for_cube(cube, locale)` which 
returns an :class:`AggregationBrowser` subclass.

The `create_workspace()` can be compared to `create_engine()` in a database 
abstraction framework and the `browser_for_cube()` can be compared to 
`engine.connect()` to get a connection from a pool.

The configuration for `create_workspace()` comes from slicer ``.ini``
configuration file in section ``[workspace]`` and is provided as ``dict``
object.
