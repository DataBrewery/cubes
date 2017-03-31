Cubes - Online Analytical Processing Framework for Python
=========================================================

[![Join the chat at https://gitter.im/DataBrewery/cubes](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/DataBrewery/cubes?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)


IMPORTANT: 2.0 Development
==========================

[![Build Status](https://travis-ci.org/DataBrewery/cubes.svg?branch=2.0)](https://travis-ci.org/DataBrewery/cubes)

This branch is under development and might be unstable or broken, especially
during work on type annotations. To work on the 2.0 branch a special
environment must be set up.

Please come back to this README regularily for changes in the environment
setup as some of the changes in external dependencies might be implemented and
publicly released.

Development Environment
-----------------------

### Types for SQLAlchemy

We need to get type stubs for SQLAlchemy from: https://github.com/JelleZijlstra/sqlalchemy-stubs

Then set your `MYPYPATH` to the path with the `sqlalchemy-stubs`

-----------------------------------------------------------------------------


[![Flattr this git repo](http://api.flattr.com/button/flattr-badge-large.png)](https://flattr.com/submit/auto?user_id=Stiivi&url=https://github.com/databrewery/cubes&title=Cubes&language=&tags=github&category=software)

Cubes is a light-weight Python framework and set of tools for Online
Analytical Processing (OLAP), multidimensional analysis and browsing of
aggregated data.

*Focus on data analysis, in human way*


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


Documentation
=============

[Latest documentation](http://cubes.readthedocs.org/en/latest)

Examples
--------

See `examples` directory in the source code repository
for simple examples and use-cases.

See https://github.com/DataBrewery/cubes-examples
for more complex examples.

Models
------

For cubes models see
https://github.com/DataBrewery/cubes-models


Development
============

Source code is in a Git repository [on GitHub](https://github.com/DataBrewery/cubes)

    git clone git://github.com/DataBrewery/cubes

After you've cloned, you might want to install all of the development dependencies.

    pip install -e .[dev]

Build the documentation like so. ::

    cd doc
    make help
    make html

Outputs will go in ``doc/_*``.


Requirements
------------

Python >= 3.6.1

Most of the requirements are soft (optional) and need to be satisfied only if
certain parts of cubes are being used.

* SQLAlchemy from http://www.sqlalchemy.org/ version >= 0.7.4 - for SQL
  backend
* Flask from http://flask.pocoo.org/ for Slicer server
* Jinja2 from http://jinja.pocoo.org/docs/ for HTML presenters

Support
=======

If you have questions, problems or suggestions, you can send a message to the
[Google group cubes-discuss](http://groups.google.com/group/cubes-discuss).

IRC channel #databrewery on server irc.freenode.net

Report bugs using [github issue
tracking](https://github.com/DataBrewery/cubes/issues).


Development
-----------

If you are browsing the code and you find something that:

* is over-complicated or not obvious
* is redundant
* can be done in better Python-way

... please let it be known.

Authors
=======

Cubes is written and maintained by Stefan Urbanek (@Stiivi on Twitter)
<stefan.urbanek@gmail.com> and various contributors. See AUTHORS file for more
information.


License
=======

Cubes is licensed under MIT license. For full license see the LICENSE file.
