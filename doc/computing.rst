Creating Cubes
++++++++++++++

The Cubes framework provides funcitonality for denormalisation and for cube pre-computation.
Currently SQL backend supports denormalisation only and mongo backend supports cube precomputation.

Relational Database (SQL)
=========================

Following code will create a denormalized view (implemented as table) from a model and
star/snowflake relational schema:

.. code-block:: python

    import sqlalchemy
    import cubes
    
    model = cubes.model_from_path("/path/to/model")

    engine = sqlalchemy.create_engine(common.staging_dburl)
    connection = engine.connect()
    cube = model.cube("contracts")

    builder = cubes.backends.SQLDenormalizer(cube, connection)
    builder.create_materialized_view("mft_contracts")

    connection.close()


Mongo Backend
=============

.. warning::

    Mongo Backed is not up-to-date with current model implementation. It might, but does not have
    to work correctly.

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

    Module :mod:`cubes.backends`.
        More information about cube builders in different database environments.

    Module :mod:`cubes`.
        Logical model description - required for preaggregated cube computation.
