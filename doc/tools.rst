Command Line Tools
******************

slicer
======

Tool for logical model and cube operations from command line.

Usage::

    slicer command [command_options]

or::
    
    slicer command sub_command [sub_command_options]

Commands are:

+-----------------------+----------------------------------------------------------------------+
| Command               | Description                                                          |
+=======================+======================================================================+
|``model validate``     | Validates logical model for OLAP cubes                               |
+-----------------------+----------------------------------------------------------------------+
|``model json``         | Create JSON representation of a model (can be used)                  |
|                       | when model is a directory.                                           |
+-----------------------+----------------------------------------------------------------------+

model validate
--------------

Usage::

    slicer model validate /path/to/model/directory
    slicer model validate model.json
    slicer model validate http://somesite.com/model.json

For more information see Model Validation in :doc:`cubes`


Example output::

    loading model wdmmg_model.json
    -------------------------
    cubes: 1
        wdmmg
    dimensions: 5
        date
        pog
        region
        cofog
        from
    -------------------------
    found 3 issues
    validation results:
    warning: No hierarchies in dimension 'date', flat level 'year' will be used
    warning: Level 'year' in dimension 'date' has no key attribute specified
    warning: Level 'from' in dimension 'from' has no key attribute specified
    0 errors, 3 warnings

model json
----------

For any given input model produce reusable JSON model.
