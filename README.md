Cubes-Lite - Online Analytical Processing Framework for Python
==============================================================

Cubes-Lite is a Python framework based on Cubes with breaking changes.
It stands for easily constructing non-standard
queries to several cubes at the same time with custom joining rules.

Cubes is a light-weight Python framework for Online
Analytical Processing (OLAP) and browsing of aggregated data
(https://github.com/DataBrewery/cubes)


Overview
========

Purpose is to provide a framework for constructing complex queries
on several cubes and be a little bit smarter than raw queries, but as much simple.

Features:

* OLAP and aggregated browsing
* Custom joining rules between each cube in model 
* Use sqlalchemy to construct queries and to get the most optimized query


Breaking changes
----------------

* removed slicer server
* removed visualizer
* removed localization
* removed authorization
* removed stores, providers, workspaces
* removed hierarchies

* added optional cuts (for different dimensions)

* redesigned model loading
* redesigned a way of aggregation

* speedup: runtime inspection of 'expression' field replaced with
manual dependencies specification


Requirements
------------

* Python >= 2.7 and Python >= 3.4.1

* SQLAlchemy from http://www.sqlalchemy.org/ version >= 0.7.4


License
=======

Cubes is licensed under MIT license. For full license see the LICENSE file.
