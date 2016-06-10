++++++++++++
Introduction
++++++++++++

Why cubes?
==========

Purpose is to provide a framework for giving analyst or any application 
end-user understandable and natural way of reporting using concept of data
Cubes – multidimensional data objects. 

It is meant to be used by application builders that want to provide analytical
functionality.

Features:

* logical view of analysed data - how analysts look at data, how they think of
  data, not how the data are physically implemented in the data stores
* OLAP and aggregated browsing (default backend is for relational database - 
  ROLAP)
* hierarchical dimensions (attributes that have hierarchical dependencies,
  such as category-subcategory or country-region)
* multiple hierarchies in a dimension
* localizable metadata and data (see :doc:`localization`)
* authentication and authorization of cubes and their data 
* pluggable data warehouse – plug-in other cube-like (multidimensional) data
  sources

The framework is very extensible.

Cube, Dimensions, Facts and Measures
====================================

The framework models the data as a cube with multiple dimensions:

.. figure:: images/cube-dims_and_cell.png
    :align: center
    :width: 400px

    a data cube
    
The most detailed unit of the data is a *fact*. Fact can be a contract,
invoice, spending, task, etc. Each fact might have a *measure* – an attribute
that can be measured, such as: price, amount, revenue, duration, tax,
discount, etc.

The *dimension* provides context for facts. Is used to:

* filter queries or reports
* controls scope of aggregation of facts
* used for ordering or sorting
* defines master-detail relationship

Dimension can have multiple *hierarchies*, for example the date dimension
might have year, month and day levels in a hierarchy.

Feature Overview
================

Core cube features:

* **Workspace** – Cubes analytical workspace
  (see :doc:`docs <workspace>`, :doc:`reference <reference/workspace>`) 
* **Model** - Description of data (*metadata*): cubes, dimensions, concept
  hierarchies, attributes, labels, localizations.
  (see :doc:`docs <model>`, :doc:`reference <reference/model>`) 
* **Browser** - Aggregation browsing, slicing-and-dicing, drill-down.
  (see :doc:`docs <slicing_and_dicing>`, :doc:`reference <reference/browser>`) 
* **Backend** - Actual aggregation implementation and utility functions.
  (see :doc:`docs <backends/index>`, :doc:`reference <reference/backends>`) 
* **Server** - WSGI HTTP server for Cubes
  (see :doc:`docs <server>`, :doc:`reference <reference/server>`) 
* **Formatters** - Data formatters
  (see :doc:`docs <formatters>`, :doc:`reference <reference/formatter>`) 
* :doc:`slicer` - command-line tool

Model
-----

Logical model describes the data from user’s or analyst’s perspective: data
how they are being measured, aggregated and reported. Model is independent of
physical implementation of data. This physical independence makes it easier to
focus on data instead on ways of how to get the data in understandable form.

More information about logical model can be found in the chapter :doc:`model`. 

See also developer's :doc:`reference <reference/model>`.

Browser
-------

Core of the Cubes analytics functionality is the aggregation browser. The 
browser module contains utility classes and functions for the 
browser to work.

More information about browser can be found in the chapter
:doc:`slicing_and_dicing`.  See also programming
:doc:`reference<reference/browser>`.

Backends
--------

Backends provide the actual data aggregation and browsing functionality. Cubes 
comes with built-in `ROLAP`_ backend which uses SQL database using 
`SQLAlchemy`_.

Framework has modular nature and supports multiple database backends,
therefore different ways of cube computation and ways of browsing aggregated
data.

Multiple backends can be used at once, even multiple sources from the same
backend might be used in the analytical workspace.

More about existing backends can be found in the :doc:`backends documentation
<backends/index>`.  See also the backends programming reference
:doc:`reference<reference/model>`.

.. _ROLAP: http://en.wikipedia.org/wiki/ROLAP
.. _SQLAlchemy: http://www.sqlalchemy.org/download.html

Server
------

Cubes comes with built-in WSGI HTTP OLAP server called :doc:`slicer` and 
provides json API for most of the cubes framework functionality. The server is 
based on the Werkzeug WSGI framework.

More information about the Slicer server requests can be found in the chapter 
:doc:`server`. See also programming reference of the :mod:`server` module.


.. seealso::

    :doc:`schemas`
        Example database schemas and use patterns with their respective
        models.
