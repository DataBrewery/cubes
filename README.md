TODO

removed slicer server as of many additional cuts
removed visualizer
removed localization
removed authorization
removed providers

redesigned model loading
redesigned browser

speedup:
removed runtime inspection of 'expression' field, instead it using manual dependencies specification

cubes_lite - Online Analytical Processing Framework for Python
==============================================================

Cubes is a light-weight Python framework for Online
Analytical Processing (OLAP) and browsing of aggregated data.


Overview
========

Purpose is to provide a framework for giving analyst or any application
end-user understandable and natural way of presenting the multidimensional
data. One of the main features is the logical model, which serves as
abstraction over physical data to provide end-user layer.

Features:

* OLAP and aggregated browsing (default backend is for relational databse -
  ROLAP)
* multidimensional analysis
* logical view of analysed data - how analysts look at data, how they think of
  data, not not how the data are physically implemented in the data stores
* hierarchical dimensions (attributes that have hierarchical dependencies,
  such as category-subcategory or country-region)
* localizable metadata and data
* SQL query generator for multidimensional aggregation queries
* OLAP server – HTTP server based on Flask Blueprint, can be [easily
  integrated](http://pythonhosted.org/cubes/deployment.html) into your
  application.


Requirements
------------

* Python >= 2.7 and Python >= 3.4.1

* SQLAlchemy from http://www.sqlalchemy.org/ version >= 0.7.4


License
=======

Cubes is licensed under MIT license. For full license see the LICENSE file.
