Architecture
============

What is inside the Cubes Python OLAP Framework? Here is a brief overview of the core modules, their purpose and functionality.

The lightweight framework Cubes is composed of four public modules:

![](http://media.tumblr.com/tumblr_lzr33cGIx41qgmvbu.png)

* *model* - Description of data (*metadata*): dimensions, hierarchies, attributes, labels, localizations.
* *browser* - Aggregation browsing, slicing-and-dicing, drill-down.
* *backends* - Actual aggregation implementation and utility functions.
* *server* - WSGI HTTP server for Cubes

Model
=====

Logical model describes the data from user’s or analyst’s perspective: data how they are being measured, aggregated and reported. Model is independent of physical implementation of data. This physical independence makes it easier to focus on data instead on ways of how to get the data in understandable form.

Cubes model is described by:

![](http://media.tumblr.com/tumblr_lzr33wXsWd1qgmvbu.png)

* model object ([doc](http://packages.python.org/cubes/model.html#cubes.model.Model))
* list of cubes
* dimensions of cubes (they are shared with all cubes within model) ([doc](http://packages.python.org/cubes/api/cubes.html#cubes.Dimension)) ([doc](http://packages.python.org/cubes/api/cubes.html#cubes.Dimension))
* hierarchies ([doc](http://packages.python.org/cubes/api/cubes.html#cubes.Hierarchy)) and hierarchy levels ([doc](http://packages.python.org/cubes/api/cubes.html#cubes.Level)) of dimensions (such as *category-subcategory*, *country-region-city*)
* optional mappings from logical model to the physical model ([doc](http://packages.python.org/cubes/model.html#attribute-mappings))
* optional join specifications for star schemas, used by the SQL denormalizing backend ([doc](http://packages.python.org/cubes/model.html#joins))

There is a utility function provided for loading the model from a JSON file: <code>load_model</code>.

The model module object are capable of being localized (see [Model Localization](http://packages.python.org/cubes/localization.html) for more information). The cubes provides localization at the metadata level (the model) and functionality to have localization at the data level.

See also: [Model Documentation](http://packages.python.org/cubes/model.html)

Browser
=======

Core of the Cubes analytics functionality is the aggregation browser. The <code>browser</code> module contains utility classes and functions for the browser to work. 

![](http://media.tumblr.com/tumblr_lzr34qlXN11qgmvbu.png)

The module components are:

* **Cell** – specification of the portion of the cube to be explored, sliced or drilled down. Each cell is specified by a set of cuts. A cell without any cuts represents whole cube.
* **Cut** – definition where the cell is going to be sliced through single dimension. There are three types of cuts: point, range and set.
    
The types of cuts:

* **Point Cut** – Defines one single point on a dimension where the cube is going to be sliced. The point might be at any level of hierarchy. The point is specified by "path". Examples of point cut: <code>[2010]</code> for *year* level of Date dimension, <code>[2010,1,7]</code> for full date point.
* **Range Cut** – Defines two points (dimension paths) on a sortable dimension between whose the cell is going to be sliced from cube.
* **Set Cut** – Defines list of multiple points (dimension paths) which are going to be included in the sliced cell.

Example of point cut effect:

![](http://media.tumblr.com/tumblr_lzr35pNwxo1qgmvbu.png)

The module provides couple utility functions:

* <code>path_from_string</code> - construct a dimension path (point) from a string
* <code>string_from_path</code> - get a string representation of a dimension path (point)
* <code>string_from_cuts</code> and <code>cuts_from_string</code> are for conversion between string and list of cuts. (Currently only list of point cuts are supported in the string representation)

The aggregation browser can:

* aggregate a cell (<code>aggregate(cell)</code>)
* drill-down through multiple dimensions and aggregate (<code>aggregate(cell, drilldown="date")</code>)
* get all detailed facts within the cell (<code>facts(cell)</code>)
* get single fact (<code>fact(id)</code>)

There is convenience function <code>report(cell, report)</code> that can be implemented by backend in more efficient way to get multiple aggregation queries in single call.

More about aggregated browsing can be found in the [Cubes documentation](http://packages.python.org/cubes/api/cubes.html#aggregate-browsing).

Backends
========

Actual aggregation is provided by the backends. The backend should implement aggregation browser interface. 

![](http://media.tumblr.com/tumblr_lzr37ayQWJ1qgmvbu.png)

Cubes comes with built-in [ROLAP](http://en.wikipedia.org/wiki/ROLAP) backend which uses SQL database through SQLAlchemy. The backend has two major components:

* *aggregation browser* that works on single denormalized view or a table
* *SQL denormalizer* helper class that converts [star schema](http://en.wikipedia.org/wiki/Star_schema) into a denormalized view or table (kind of materialisation).

There was an attempt to write a [Mongo DB backend](https://github.com/Stiivi/cubes/tree/master/cubes/backends/mongo), but it does not work any more, it is included in the sources only as reminder, that there should be a mongo backend sometime in the future.

Anyone can write a backend. If you are interested, drop me a line.

Server
======

Cubes comes with Slicer - a WSGI HTTP OLAP server with API for most of the cubes framework functionality. The server is based on the Werkzeug framework.

![](http://media.tumblr.com/tumblr_lzr37v5B6G1qgmvbu.png)

Intended use of the slicer is basically as follows:

* application prepares the cell to be aggregated, drilled, listed... The *cell* might be whole cube.
* HTTP request is sent to the server
* the server uses appropriate aggregation browser backend (note that currently there is only one: SQL denormalized) to compute the request
* Slicer returns a JSON reply to the application

For more information, please refer to the Cubes [Slicer server documentation](http://packages.python.org/cubes/server.html).

One more thing...
=================

There are plenty things to get improved, of course. Current focus is not on performance, but on achieving simple usability.

The Cubes sources can be found on Github: https://github.com/stiivi/cubes. There is also a IRC channel #databrewery on irc.freenode.net (I try to be there during late evening CET). Issues can be reported on the [github project page](https://github.com/stiivi/cubes/issues?sort=created&direction=desc&state=open).

If you have any questions, suggestions, recommendations, just let me know.

