*******************************
HTTP WSGI OLAP Server Reference
*******************************

.. module:: server
   :synopsis: HTTP WSGI Server

Light-weight HTTP WSGI server based on the `Flask`_ framework. For more
information about using the server see :doc:`../server`.

.. _Flask: http://flask.pocoo.org/

.. data:: cubes.server.slicer

    Flask Blueprint instance.
    
    See :doc:`../recipes/flask_integration` for a use example.

.. data:: cubes.server.workspace

    Flask `Local` object referring to current application's workspace.

.. autofunction:: cubes.server.run_server
.. autofunction:: cubes.server.create_server


