++++++++++++++++++++++
Removed Documentation
++++++++++++++++++++++

This file contains removed documentation (might be obsolete) that might be useful in the future. 

Aggregation
===========

    * ``Cell`` is no longer used for browsing, you use only ``Browser`` and pass a cell as first argument
      to get aggregated or other results.
    * Mongo backend is no logner maintained, only ``cubes.backends.sql.SQLBrowser`` is available

This is MongoDB example, other systems coming soon.

First you have to prepare logical model and cube. In relational database:

.. code-block:: python

    import cubes
    
    # connection is SQLAlchemy database connection
    
    # Create aggregation browser
    browser = cubes.backends.SQLBrowser(cube, connection, "mft_contracts")

To browse localized data, just pass locale to the browser and all results will contain localized
values for localizable attributes:

.. code-block:: python

    browser = cubes.backends.SQLBrowser(cube, connection, "mft_contracts", locale = "sk")

To browse pre-aggregated mongo data:

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

Prepare aggregation browser:

.. code-block:: python

    browser = cubes.browse.MongoSimpleCubeBrowser(cube = cube, 
                                                         collection = "cube",
                                                         database = database)

    # Get the whole cube
    full_cube = browser.full_cube()

Following aggregation code is backend-independent. Aggregate all data for year 2009:

.. code-block:: python

    cuboid = full_cube.slice("date", ['2009'])
    results = cuboid.aggregate()
    
Results will contain one aggregated record.

Drill down through a dimension:

.. code-block:: python

    results_cofog = cuboid.aggregate(drill_down = "cofog")
    results_date = cuboid.aggregate(drill_down = "date")

`results_cofog` will contain all aggregations for "cofog" dimension at level 1 within year 2009.
`results_date` will contain all aggregations for month within year 2009.

Drilling-down and aggregating through single dimension. Following function will print aggregations
at each level of given dimension.

.. code-block:: python

    def expand_drill_down(dimension_name, path = []):

        dimension = cube.dimension(dimension_name)
        hierarchy = dimension.default_hierarchy

        # We are at last level, nothing to drill-down
        if hierarchy.path_is_base(path):
            return

        # Construct cuboid of our interest
        full_cube = browser.full_cube()
        cuboid = full_cube.slice("date", ['2009'])
        cuboid = cuboid.slice(dimension_name, path)
    
        # Perform aggregation
        cells = cuboid.aggregate(drill_down = dimension_name)

        # Print results
        prefix = "    " * len(path)
        for cell in cells:
            path = cell["_cell"][dimension_name]
            current = path[-1]
            print "%s%s: %.1f %d" % (prefix, current, cell["amount_sum"], cell["record_count"])
            expand_drill_down(dimension_name, path)

The internal key `_cell` contains a dictionary with aggregated cell reference in form: ``{dimension:
path}``, like ``{ "date" = [2010, 1] }``

.. note::

    The output record from aggregations will change into an object instead of a dictionary, in the
    future. The equivalent to the _cell key will be provided as an object attribute.

Assume we have two levels of date hierarhy: `year`, `month`. To get all time-based drill down:

.. code-block:: python
    
    expand_drill_down("date")
    
Possible output would be::

    2008: 1200.0 60
        1: 100.0 10
        2: 200.0 5
        3: 50.0 1
        ...
    2009: 2000.0 10
        1: 20.0 10
        ...

    


