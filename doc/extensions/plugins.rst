****************
Plugin Reference
****************

Cubes has a plug-in based architecture. The objects that can be provided
through external plug-ins are: `authenticators`, `authorizers`, `browsers`, `formatters`,
`model_providers` and `stores`.

Plugins are classes providing an interface respective for the plug-in class.
They are advertised throgh ``setup.py`` as follows:

.. code-block:: python

    setup(
        name = "my_package",

        # ... regular module setup here

        # Cubes Plugin Advertisment
        #
        entry_points={
            'cubes.stores': [
                'my = my_package.MyStore',
            ],
            'cubes.authorizers': [
                'my = my_package.MyAuthorizer',
            ]
        }
    )


For more information see `Python Packaging User Guide
<https://packaging.python.org/en/latest/distributing/#entry-points>`_
