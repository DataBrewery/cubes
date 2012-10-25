Cubes - Online Analytical Processing Framework for Python
=========================================================

About
-----

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
-------------

Documentation can be found at: http://packages.python.org/cubes

See `examples` directory for simple examples and use-cases. Also see:

    https://github.com/stiivi/cubes-examples
    
for more complex examples.


Source
------

Github source repository: https://github.com/Stiivi/cubes

Requirements
------------

Developed using python 2.7.

Most of the requirements are soft (optional) and need to be satisfied only if 
certain parts of cubes are being used.

* SQLAlchemy from http://www.sqlalchemy.org/ version >= 0.7.1 - for SQL
  backend
* Werkzeug from http://werkzeug.pocoo.org/ for Slicer server
* Jinja2 from http://jinja.pocoo.org/docs/ for HTML presenters

Support
=======

If you have questions, problems or suggestions, you can send a message to the 
Google group or write to the author.

* Google group: http://groups.google.com/group/cubes-discuss
* IRC channel #databrewery on server irc.freenode.net

Report bugs using github issue tracking: https://github.com/Stiivi/cubes/issues

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

Cubes is licensed under MIT license with following addition:

    If your version of the Software supports interaction with it remotely 
    through a computer network, the above copyright notice and this permission 
    notice shall be accessible to all users.

Simply said, that if you use it as part of software as a service (SaaS) you 
have to provide the copyright notice in an about, legal info, credits or some 
similar kind of page or info box.

For full license see the LICENSE file.
