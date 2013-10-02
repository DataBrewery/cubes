***************
Model Reference
***************

Model - Cubes meta-data objects and functionality for working with them.
:doc:`../model`

.. seealso::

    :doc:`providers`
        Model providers – objects for constructing model objects from other
        kinds of sources, even during run-time.


Creating model objects from metadata
====================================

Following methods are used to create model objects from a metadata dicitonary.

.. autofunction:: cubes.create_cube
.. autofunction:: cubes.create_dimension
.. autofunction:: cubes.create_level
.. autofunction:: cubes.create_attribute
.. autofunction:: cubes.create_measure
.. autofunction:: cubes.create_measure_aggregate
.. autofunction:: cubes.attribute_list

Model components
================

.. note::

    The `Model` class is no longer publicly available and should not be used.
    For more information, please see :class:`cubes.Workspace`.

Cube
----

.. autoclass:: cubes.Cube

Dimension, Hierarchy and Level
------------------------------

.. autoclass:: cubes.Dimension

.. autoclass:: cubes.Hierarchy

.. autoclass:: cubes.Level

Attributes, Measures and Aggregates
-----------------------------------

.. autoclass:: cubes.AttributeBase
.. autoclass:: cubes.Attribute
.. autoclass:: cubes.Measure
.. autoclass:: cubes.MeasureAggregate

.. exception:: ModelError

   Exception raised when there is an error with model and its structure, mostly 
   during model construction.

.. exception:: ModelIncosistencyError

    Raised when there is incosistency in model structure, mostly when model
    was created programatically in a wrong way by mismatching classes or
    misonfiguration.

.. exception:: NoSuchDimensionError

    Raised when a dimension is requested that does not exist in the model.

.. exception:: NoSuchAttributeError

    Raised when an unknown attribute, measure or detail requested.

