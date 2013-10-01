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
.. autoclass:: cubes.backends.sql.browser.QueryContext

.. note::

   :class:`cubes.QueryContext` does not serve to it's original purpose anymore
   and will be verylikely meerged with the browser.

Slicer
======

This backend is just for backend development demonstration purposes.

.. autoclass:: cubes.backends.slicer.SlicerBrowser

Mixpanel
========

.. autoclass:: cubes.backends.mixpanel.browser.MixpanelBrowser

Mongo DB
========

.. autoclass:: cubes.backends.mongo2.browser.Mongo2Browser
