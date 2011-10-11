Installation
++++++++++++

Optional requirements:

* `SQLAlchemy`_ for SQL backend
* `Werkzeug`_ for Slicer server

.. _SQLAlchemy: http://www.sqlalchemy.org/download.html
.. _Werkzeug: http://werkzeug.pocoo.org/

To install cubes, you can use ``easy_install`` (from `setuptools`_)::

    easy_install cubes

or ``pip``::
    
    pip install cubes
    
Main project repository at Github: https://github.com/Stiivi/cubes

Bitbucket copy for mercurial users: https://bitbucket.org/Stiivi/cubes (might be lagging a little bit
behind github).


From sources
~~~~~~~~~~~~

Download from Github::

    git clone git://github.com/Stiivi/cubes.git

Install::

    cd cubes
    python setup.py install

.. _setuptools: http://pypi.python.org/pypi/setuptools

Indirect dependencies
~~~~~~~~~~~~~~~~~~~~~

For PostgreSQL, you have to install ``psycopg2`` or some other SQL Alchemy postgres backend.
