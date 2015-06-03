*****************************
Aggregation Browsing Backends
*****************************

Built-in backends for browsing aggregates of various data sources.

Other backends can be found at https://github.com/DataBrewery.

SQL
===

SQL backend uses SQLAlchemy for generating queries. It supports all databases
that the SQLAlchemy supports such as:

* Drizzle
* Firebird
* Informix
* Microsoft SQL Server
* MySQL
* Oracle
* PostgreSQL
* SQLite
* Sybase


Browser
-------

.. autoclass:: cubes.sql.browser.SQLBrowser
.. autoclass:: cubes.sql.query.StarSchema
.. autoclass:: cubes.sql.query.QueryContext
.. autofunction:: cubes.sql.query.to_column
.. autofunction:: cubes.sql.query.to_join_key
.. autofunction:: cubes.sql.query.to_join

Slicer
======

.. autoclass:: cubes.server.browser.SlicerBrowser
