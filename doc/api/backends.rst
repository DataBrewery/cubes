*************************************************
:mod:`backends` --- Aggregation Browsing Backends
*************************************************

.. module:: backends
   :synopsis: backends for browsing aggregates of various data sources

SQL
===

The standard SQL backend provides full-featured aggregation browser of denormalized data source. The helper class ``SQLDenormalizer`` creates view or a table from a star or snowflake schema. The created view is then passed to the borwser for slicing and dicing.

.. autoclass:: cubes.backends.sql.SQLDenormalizer
.. autoclass:: cubes.backends.sql.SQLBrowser


