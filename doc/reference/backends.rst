*****************************
Aggregation Browsing Backends
*****************************

Backends for browsing aggregates of various data sources

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

.. autoclass:: cubes.backends.sql.browser.SnowflakeBrowser
.. autoclass:: cubes.backends.sql.query.QueryBuilder
.. autoclass:: cubes.backends.sql.mapper.SnowflakeMapper

Slicer
======

.. autoclass:: cubes.backends.slicer.SlicerBrowser

Mixpanel
========

.. autoclass:: cubes.backends.mixpanel.browser.MixpanelBrowser

Mongo DB
========

.. autoclass:: cubes.backends.mongo2.browser.Mongo2Browser
.. autoclass:: cubes.backends.mongo2.mapper.MongoCollectionMapper
