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

.. seealso::

    Module :mod:`backends`.
        More information about cube builders in different database environments.

    Module :mod:`model`.
        Logical model description - required for preaggregated cube computation.
