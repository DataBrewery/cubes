Computing Cubes
+++++++++++++++

Example of cube precomputation for Where Does My Money Go in a MongoDB database. Source is single 
database collection containing facts with multiple dimensions and single measure `amount`. There
is one dimension that is required for all aggregations: `date` (not listed, as it is required
by default).

See this simplified wdmmg:download:`logical model example <wdmmg_model.json>` for cube metadata
(dimensions, levels, hierarchies, ...).

.. code-block:: python

    import cubes
    import pymongo

    # Create MongoDB database connection
    connection = pymongo.Connection()
    database = connection["wdmmg_dev"]

    # Load model and get cube
    model_path = "wdmmg_model.json"
    model = cubes.model_from_path(model_path)
    cube = model.cubes["wdmmg"]

    # Create cube builder: facts are read from collection named "entry", aggregations
    # are inserted into collection named "cube"
    
    builder = cubes.builders.MongoSimpleCubeBuilder(cube, database,
                                            fact_collection = "entry",
                                            cube_collection = "cube")

    # Compute the cube!
    builder.compute()

API
===


.. seealso::

    Module :mod:`cubes.builders`.
        More information about cube builders in different database environments.

    Module :mod:`cubes`.
        Logical model description - required for preaggregated cube computation.
