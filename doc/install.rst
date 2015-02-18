++++++++++++
Installation
++++++++++++

There are two options how to install cubes: basic common installation - 
recommended mostly for users starting with Cubes. Then there is customized 
installation with requirements explained.

Basic Installation
==================

The cubes has optional requirements:

* `SQLAlchemy`_ for SQL database aggregation browsing backend (version >=
  0.7.4)
* `Flask`_ for Slicer OLAP HTTP server

.. note::

    If you never used Python before, you might have to get the `pip installer`_ 
    first, if you do not have it already.
    
.. note::

    The command-line tool :doc:`Slicer<slicer>` does not require knowledge of 
    Python. You do not need to know the language if you just want to 
    :doc:`serve<server>` OLAP data.

You may install Cubes with the minimal dependencies, ::

    pip install cubes

with certain extras (html, sql, mongo, or slicer), ::

    pip install cubes[slicer]

or with all of the extras. ::

    pip install cubes[all]

If you are developing cubes, you should install ``cubes[all]``.

.. _SQLAlchemy: http://www.sqlalchemy.org/download.html
.. _Flask: http://flask.pocoo.org/
.. _pip installer: http://www.pip-installer.org/en/latest/installing.html#install-or-upgrade-pip

Quick Start or Hello World!
===========================

Download the sources from the `Cubes Github repository`_. Go to the 
``examples/hello_world`` folder::

    git clone git://github.com/DataBrewery/cubes.git
    cd cubes
    cd examples/hello_world

Prepare data and run the :doc:`OLAP server<server>`::

    python prepare_data.py
    slicer serve slicer.ini
    
And try to do some queries::

    curl "http://localhost:5000/cube/irbd_balance/aggregate"
    curl "http://localhost:5000/cube/irbd_balance/aggregate?drilldown=year"
    curl "http://localhost:5000/cube/irbd_balance/aggregate?drilldown=item"
    curl "http://localhost:5000/cube/irbd_balance/aggregate?drilldown=item&cut=item:e"

.. _Cubes Github repository: https://github.com/DataBrewery/cubes

Customized Installation
=======================

The project sources are stored in the `Github repository`_.

.. _Github repository: https://github.com/DataBrewery/cubes

Download from Github::

    git clone git://github.com/DataBrewery/cubes.git

Install::

    cd cubes
    pip install -r requirements.txt
    pip install -r requirements-optional.txt
    python setup.py install

.. note::

    The requirements for SQLAlchemy_ and Flask_ are optional and you do not
    need them if you are going to use another kind of backend or don't going
    to use the Slicer server.

