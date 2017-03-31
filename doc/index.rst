######################
Cubes - OLAP Framework
######################

Cubes is a light-weight Python framework and set of tools for development of
reporting and analytical applications, Online Analytical Processing (OLAP),
multidimensional analysis and browsing of aggregated data.  It is part of
`Data Brewery`_.

.. _Data Brewery: http://databrewery.org/

Getting Started
---------------

.. toctree::
    :maxdepth: 2

    introduction
    install
    related
    tutorial
    credits

Data Modeling
-------------

.. toctree::
    :maxdepth: 2

    model
    schemas
    localization

Aggregation, Slicing and Dicing
-------------------------------

.. toctree::
    :maxdepth: 2

    slicing_and_dicing
    formatters

Analytical Workspace
--------------------

.. toctree::
    :maxdepth: 2

    workspace
    auth
    configuration
    backends/sql
    backends/slicer

Slicer Server and Tool
----------------------

.. toctree::
    :maxdepth: 2

    server
    deployment
    slicer

Recipes
-------

.. toctree::
    :maxdepth: 2

    recipes/index

Extension Development
---------------------

.. toctree::
    :maxdepth: 2

    extensions/plugins
    extensions/backends
    extensions/providers
    extensions/auth

Developer's Reference
---------------------

.. toctree::
    :maxdepth: 2

    reference/workspace
    reference/model
    reference/providers
    reference/browser
    reference/formatter
    reference/backends
    reference/server
    reference/auth
    reference/common

Release Notes
-------------

.. toctree::
    :maxdepth: 2

    releases/index

Contact and Getting Help
========================

Join the chat at `Gitter`_.

If you have questions, problems or suggestions, you can send a message to 
`Google group`_ or `write to the author`_ (Stefan Urbanek).

Report bugs in `github issues`_ tracking

.. _Gitter: https://gitter.im/DataBrewery/cubes
.. _github issues: https://github.com/DataBrewery/cubes/issues
.. _Google group: http://groups.google.com/group/cubes-discuss
.. _write to the author: stefan.urbanek@gmail.com

There is an IRC channel ``#databrewery`` on server ``irc.freenode.net``.

License
-------

Cubes is licensed under MIT license with small addition::

    Copyright (c) 2011-2014 Stefan Urbanek, see AUTHORS for more details

    Permission is hereby granted, free of charge, to any person obtaining a 
    copy of this software and associated documentation files (the "Software"), 
    to deal in the Software without restriction, including without limitation 
    the rights to use, copy, modify, merge, publish, distribute, sublicense, 
    and/or sell copies of the Software, and to permit persons to whom the 
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in 
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
    DEALINGS IN THE SOFTWARE.

Simply said, that if you use it as part of software as a service (SaaS) you 
have to provide the copyright notice in an about, legal info, credits or some 
similar kind of page or info box.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
