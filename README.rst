Cubes - Online Analytical Processing Framework for Python
=========================================================

Cubes is a light-weight Python framework and set of tools for Online
Analytical Processing (OLAP), multidimensional analysis and browsing of
aggregated data. 

*Focus on data analysis, in human way*

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
* OLAP server (WSGI HTTP server with JSON API based on Wergzeug)

Documentation
=============

Manual
------

Latest release documentation: http://packages.python.org/cubes

Development documentation: http://cubes.databrewery.org/dev/doc

Examples
--------

See ``examples`` directory in the source code repository
for simple examples and use-cases.

See https://github.com/DataBrewery/cubes-examples
for more complex examples.

Models
------

For cubes models see
https://github.com/DataBrewery/cubes-models


Development
============
Source code is in a Git repository `on GitHub <https://github.com/DataBrewery/cubes>`_. ::

    git clone git://github.com/DataBrewery/cubes

After you've cloned, you might want to install all of the development dependencies. ::

    pip install -e .[dev]

Build the documentation like so. ::

    cd doc
    make help
    make html

Outputs will go in ``doc/_*``.

Requirements
------------

Python >= 2.7 and Python >= 3.4.1


Most of the requirements are soft (optional) and need to be satisfied only if 
certain parts of cubes are being used.

* SQLAlchemy from http://www.sqlalchemy.org/ version >= 0.7.4 - for SQL
  backend
* Werkzeug from http://werkzeug.pocoo.org/ for Slicer server
* Jinja2 from http://jinja.pocoo.org/docs/ for HTML presenters
* PyMongo for mongo and mongo2 backend
* pytz for mongo2 backend

Support
=======

If you have questions, problems or suggestions, you can send a message to the 
Google group or write to the author.

* Google group: http://groups.google.com/group/cubes-discuss
* IRC channel #databrewery on server irc.freenode.net

Report bugs using github issue tracking: https://github.com/DataBrewery/cubes/issues


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

Cubes is licensed under MIT license with following addition.

> If your version of the Software supports interaction with it remotely 
> through a computer network, the above copyright notice and this permission 
> notice shall be accessible to all users.

Simply said, that if you use it as part of software as a service (SaaS) you 
have to provide the copyright notice in an about, legal info, credits or some 
similar kind of page or info box.

For full license see the LICENSE file.
