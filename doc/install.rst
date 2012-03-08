++++++++++++
Installation
++++++++++++


Requirements and Dependencies
=============================

The cubes has optional requirements (weak dependency):

* `SQLAlchemy`_ for SQL database aggregation browsing backend
* `Werkzeug`_ for Slicer WSGI server

It is recommended to install them, but not necessary. If you are first-time 
user, you are quite likely going to need them::

    easy_install sqlalchemy werkzeug

For PostgreSQL, you should install ``psycopg2`` or some other SQLAlchemy 
postgres backend::

    easy_install psycopg2

.. _SQLAlchemy: http://www.sqlalchemy.org/download.html
.. _Werkzeug: http://werkzeug.pocoo.org/

Installation
============

To install cubes, you can use ``easy_install`` (from `setuptools`_)::

    easy_install cubes

or ``pip``::
    
    pip install cubes
    
Main project `repository at Github`_.

.. _repository at Github: https://github.com/Stiivi/cubes

.. note::

    There was once a `Bitbucket repository`_ copy for mercurial users, however 
    this one is no longer updated.

.. _Bitbucket repository: https://github.com/Stiivi/cubes

From sources
------------

Download from Github::

    git clone git://github.com/Stiivi/cubes.git

Install::

    cd cubes
    python setup.py install

.. _setuptools: http://pypi.python.org/pypi/setuptools
