******************************
:mod:`model` --- Logical Model
******************************

.. module:: model
   :synopsis: logical model representation, cube descriptions, dimensions

:mod:`model` is a package that provides Cubes meta-data objects and functionality for working with them. :doc:`../model`
   
.. figure:: images/model-package.png
    :align: center
    :width: 300px

    The logical model classes.

   
Loading a model
===============

.. autofunction:: cubes.model.load_model

Model components
================

Model
-----

.. autoclass:: cubes.model.Model

Cube
----

.. autoclass:: cubes.model.Cube

Dimension, Hierarchy, Level
---------------------------

.. autoclass:: cubes.model.Dimension

.. autoclass:: cubes.model.Hierarchy

.. autoclass:: cubes.model.Level

.. autoclass:: cubes.model.Attribute

Helper function to coalesce list of attributes, which can be provided as strings or as Attribute objects:

.. autofunction:: cubes.attribute_list

.. exception:: ModelError

   Exception raised when there is an error with model and its structure, mostly 
   during model construction.
