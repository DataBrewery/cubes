Cubes - Online Analytical Processing Framework for Python
=========================================================

About
-----

Cubes is a light-weight Python framework for:

* Online Analytical Processing - OLAP
* multidimensional analysis
* cube computation

Framework is database agnostic, has modular backend architecture. Currently supports:

* relational databases with SQL (through SQL Alchemy)

Did support once in history, code is kept intentionally:

* MongoDB (not working anymore, is missing maintainer/developer)


**Follow @DataBrewery** on Twitter for updates.

Documentation
-------------

Documentation can be found at: http://packages.python.org/cubes

Source
------

Github source repository: https://github.com/Stiivi/cubes

Requirements
------------

Developed using python 2.7, reported to work with 2.6.

Most of the requirements are soft (optional) and need to be satisfied only if certain parts of cubes are
being used.

* SQLAlchemy from http://www.sqlalchemy.org/ version >= 0.7.1 - for SQL backend
* Werkzeug from http://werkzeug.pocoo.org/ for Slicer server
* PyMogno - for MongoDB backend

Support
=======

If you have questions, problems or suggestions, you can send a message to the Google group or 
write to the author.

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

Cubes is written and maintained by Stefan Urbanek @Stiivi <stefan.urbanek@gmail.com> and various
contributors. See AUTHORS file for more information.

License
=======

Cubes is licensed under MIT license with following addition:

    If your version of the Software supports interaction with it remotely through a computer network, the
    above copyright notice and this permission notice shall be accessible to all users.

Simply said, that if you use it as part of software as a service (SaaS) you have to provide the copyright notice in an about, legal info, credits or some similar kind of page or info box.

For full license see the LICENSE file.
