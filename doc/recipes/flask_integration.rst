**********************************
Integration With Flask Application
**********************************

Objective: Add Cubes Slicer to your application to provide raw analytical
data.

Cubes Slicer Server can be integrated with your application very easily. The
Slicer is provided as a flask Blueprint – a module that can be plugged-in.

The following code will add all Slicer's end-points to your application:

.. code-block:: python

    from flask import Flask
    from cubes.server import slicer

    app = Flask(__name__)
    app.register_blueprint(slicer, config="slicer.ini")

To have a separate sub-path for Slicer add `url_prefix`:

.. code-block:: python

    app.register_blueprint(slicer, url_prefix="/slicer", config="slicer.ini")

.. seealso::

    `Flask – Modular Applications with Blueprints <http://flask.pocoo.org/docs/blueprints/>`_

    :doc:`../reference/server`

