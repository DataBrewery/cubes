++++++++++++
Installation
++++++++++++

There are two options how to install cubes: basic common installation - 
recommended mostly for users starting with Cubes. Then there is customized 
installation with requirements explained.

Basic Installation
==================

The cubes has optional requirements:

* `SQLAlchemy`_ for SQL database aggregation browsing backend
* `Werkzeug`_ for Slicer WSGI server

.. note::

    If you never used Python before, you might have to get the `pip installer`_ 
    first, if you do not have it already.
    
.. note::

    The command-line tool :doc:`Slicer<slicer>` does not require knowledge of 
    Python. You do not need to know the language if you just want to 
    :doc:`serve<server>` OLAP data.

For quick satisfaction of requirements install the packages::

    pip install sqlalchemy werkzeug

Then install the Cubes::

    pip install cubes

.. _SQLAlchemy: http://www.sqlalchemy.org/download.html
.. _Werkzeug: http://werkzeug.pocoo.org/
.. _pip installer: http://www.pip-installer.org/

Quick Start or Hello World!
===========================

Download the sources from the `Cubes Github repository`_. Go to the 
``examples/hello_world`` folder::

    git clone git://github.com/Stiivi/cubes.git
    cd cubes
    cd examples/hello_world

Prepare data and run the :doc:`OLAP server<server>`::

    python prepare_data.py
    slicer serve slicer.ini
    
And try to do some queries::

    curl "http://localhost:5000/aggregate"
    curl "http://localhost:5000/aggregate?drilldown=year"
    curl "http://localhost:5000/aggregate?drilldown=item"
    curl "http://localhost:5000/aggregate?drilldown=item&cut=item:e"

.. _Cubes Github repository: https://github.com/Stiivi/cubes

Customized Installation
=======================

The project sources are stored in the `Github repository`_.

.. _Github repository: https://github.com/Stiivi/cubes

Download from Github::

    git clone git://github.com/Stiivi/cubes.git

The requirements for SQLAlchemy_ and Werkzeug_ are optional and you do not need
them if you are going to use another kind of backend.

Install::

    cd cubes
    pip install -r requirements-optional.txt
    python setup.py install

