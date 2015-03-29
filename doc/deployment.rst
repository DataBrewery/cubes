*****************
Server Deployment
*****************

Apache mod_wsgi deployment
==========================

Deploying Cubes OLAP Web service server (for analytical API) can be done in
four very simple steps:

1. Create slicer server :doc:`configuration` file
2. Create WSGI script
3. Prepare apache site configuration
4. Reload apache configuration

.. note::

    The model paths have to be full paths to the model, not relative paths to
    the configuration file.

Place the file in the same directory as the following WSGI script (for
convenience).

Create a WSGI script ``/var/www/wsgi/olap/procurements.wsgi``:

.. code-block:: python

    import os.path
    from cubes.server import create_server

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

    # Set the configuration file name (and possibly whole path) here
    CONFIG_PATH = os.path.join(CURRENT_DIR, "slicer.ini")

    application = create_server(CONFIG_PATH)


Apache site configuration (for example in ``/etc/apache2/sites-enabled/``)::

    <VirtualHost *:80>
        ServerName olap.democracyfarm.org

        WSGIScriptAlias /vvo /var/www/wsgi/olap/procurements.wsgi

        <Directory /var/www/wsgi/olap>
            WSGIProcessGroup olap
            WSGIApplicationGroup %{GLOBAL}
            Order deny,allow
            Allow from all
        </Directory>

        ErrorLog /var/log/apache2/olap.democracyfarm.org.error.log
        CustomLog /var/log/apache2/olap.democracyfarm.org.log combined

    </VirtualHost>

Reload apache configuration::

    sudo /etc/init.d/apache2 reload


UWSGI
=====

Configuration file ``uwsgi.ini``:

.. code-block:: ini

    [uwsgi]
    http = 127.0.0.1:5000
    module = cubes.server.app
    callable = application

Run ``uwsgi uwsgi.ini``.

You can set environment variables:

* ``SLICER_CONFIG`` – full path to the slicer configuration file
* ``SLICER_DEBUG`` – set to true boolean value if you want to enable Flask
  server debugging

Heroku and UWSGI
================

To deploy the slicer in Heroku, prepare a directory with following files:

* ``slicer.ini`` – main slicer configuration file
* ``uwsgi.ini`` – UWSGI configuration
* ``Procfile``

The ``Procfile``::

    web: uwsgi uwsgi.ini

The ``uwsgi.ini``:

.. code-block:: ini

    [uwsgi]
    http-socket = :$(PORT)
    master = true
    processes = 4
    die-on-term = true
    memory-report = true
    module = cubes.server.app

The ``requirements.txt``::

    Flask
    SQLAlchemy
    -e git+git://github.com/DataBrewery/cubes.git@master#egg=cubes
    jsonschema
    python-dateutil
    expressions
    grako
    uwsgi

Add any packages that you might need for your Slicer server installation.
