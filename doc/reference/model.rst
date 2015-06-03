***************
Model Reference
***************

Model - Cubes meta-data objects and functionality for working with them.
:doc:`../model`

.. note::

    All model objects: `Cube`, `Dimension`, `Hierarchy`, `Level` and attribute
    objects should be considered immutable once created. Any changes to the
    object attributes might result in unexpected behavior.

.. seealso::

    :doc:`providers`
        Model providers – objects for constructing model objects from other
        kinds of sources, even during run-time.


Model Utility Functions
=======================

.. autofunction:: cubes.object_dict
.. autofunction:: cubes.create_list_of
.. autofunction:: cubes.collect_attributes
.. autofunction:: cubes.collect_dependencies
.. autofunction:: cubes.depsort_attributes


Model components
================

.. autoclass:: cubes.ModelObject

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

