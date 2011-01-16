OLAP Cubes
**********

Note: For Cubes API see :mod:`cubes`.

Logical Model
=============

.. figure:: logical_model.png

   The logical model entities and relationships.
   
Create a model::

    model = cubes.model_from_path(path)

The ``path`` is a directory with logical model description files.

Model can be represented also as a single json file containing all model objects. 

Original design decision for directory based models was because of easier copying of model
objects (dimensions, cubes) from one model to another without requirements for any special
tools - filesystem copy would be sufficient.

Logical Model description
-------------------------


========================== =============================================
File                       Description
========================== =============================================
model.json                 Core model information
cube_*cube_name*.json      Cube description, one file per cube
dim_*dimension_name*.json  Dimension description, one file per dimension
========================== =============================================


model.json
++++++++++

The ``model.json`` contains main model description dictionary. The file looks like this::

    {
    	"name": "public_procurements",
    	"label": "Public Procurements of Slovakia",
    	"description": "Contracts of public procurement winners in Slovakia"
    }

============== ===================================================
Key            Description
============== ===================================================
name           dimension name
label          human readable name - can be used in an application
description    longer human-readable description of the model
============== ===================================================

Dimension descriptions
++++++++++++++++++++++

Dimension descriptions are stored in json files with prefix ``dim_`` like ``dim_supplier``, or as
a dictionary for key ``dimensions`` in the model description dictionary.

.. figure:: dimension_desc.png

   Dimension description - attributes.


The dimension description contains keys:

============== ===================================================
Key            Description
============== ===================================================
name           dimension name
label          human readable name - can be used in an application
levels         dictionary of hierarchy levels
attributes     dictionary of dimension attributes
hierarchies    dictionary of dimension hierarchies
============== ===================================================

Example::

    {
        "name": "date",
        "label": "Dátum",
        "levels": { ... }
        "attributes": { ... }
        "hierarchies": { ... }
    }

Hierarchy levels are described:

================ ================================================================
Key              Description
================ ================================================================
label            human readable name - can be used in an application
key              key field of the level (customer number for customer level,
                 region code for region level, year-month for month level). key
                 will be used as a grouping field for aggregations. Key should be
                 unique within level.
label_attribute  name of attribute containing label to be displayed (customer
                 name for customer level, region name for region level,
                 month name for month level)
attributes       list of other additional attributes that are related to the
                 level. The attributes are not being used for aggregations, they
                 provide additional useful information.
================ ================================================================

Example of month level of date dimension::

    "month": {
        "label": "Mesiac",
        "key": "month",
        "label_attribute": "month_name",
        "attributes": ["month", "month_name", "month_sname"]
    },
    
Example of supplier level of supplier dimension::

    "supplier": {
        "label": "Dodávateľ",
        "key": "ico",
        "label_attribute": "name",
        "attributes": ["ico", "name", "address", "date_start", "date_end",
                        "legal_form", "ownership"]
    }

Hierarchies are described:

================ ================================================================
Key              Description
================ ================================================================
label            human readable name - can be used in an application
levels           ordered list of level names from top to bottom - from least
                 detailed to most detailed (for example: from year to day, from
                 country to city)
================ ================================================================

Example::

    "hierarchies": {
        "default": {
            "levels": ["year", "month"]
        },
        "ymd": {
            "levels": ["year", "month", "day"]
        },
        "yqmd": {
            "levels": ["year", "quarter", "month", "day"]
        }
    }


Cube descriptions
+++++++++++++++++

Cube descriptions are stored in json files with prefix ``cube_`` like ``cube_contracts``, or as
a dictionary for key ``cubes`` in the model description dictionary.

============== ====================================================
Key            Description
============== ====================================================
name           dimension name
label          human readable name - can be used in an application
measures       list of cube measures
dimensions     list of cube dimensions
joins          specification of physical table joins
mappings       mapping of logical attributes to physical attributes
============== ====================================================

Example::

    {
        "name": "date",
        "label": "Dátum",
        "dimensions": [ "date", ... ]
        "joins": { ... }
        "mappings": { ... }
    }

Model validation
================
To validate a model do::

    results = model.validate()
    
This will return a list of tuples (result, message) where result might be 'warning' or 'error'.
If validation contains errors, the model can not be used without resulting in failure. If there
are warnings, some functionalities might or might not fail or might not work as expected.

You can validate model from command line::

    slicer model validate /path/to/model

Errors
------

+----------------------------------------+----------------------------------------------------+
| Error                                  | Resolution                                         |
+========================================+====================================================+
| No mappings for cube *a cube*          | Provide mappings dictionary for cube               |
+----------------------------------------+----------------------------------------------------+
| No mapping for measure *a measure* in  | Add mapping for *a measure* into mappings          |
| cube *a cube*                          | dictionary                                         |
+----------------------------------------+----------------------------------------------------+
| No levels in dimension *a dimension*   | Define at least one dimension level.               |
+----------------------------------------+----------------------------------------------------+
| No hierarchies in dimension            | Define at least one hierarchy.                     |
| *a dimension*                          |                                                    |
+----------------------------------------+----------------------------------------------------+
| No defaut hierarchy specified, there is| Specify a default hierarchy name or name one       |
| more than one hierarchy in dimension   | hierarchy as ``default``                           |
| *a dimension*                          |                                                    |
+----------------------------------------+----------------------------------------------------+
| Level *a level* in dimension           | Provide level attributes. At least one - the level |
| *a dimension* has no attributes        | key.                                               |
+----------------------------------------+----------------------------------------------------+
| Key *a key* in level *a level* in      | Add key attribute into attribute list or check     |
| dimension *a dimension* is not in      | the key name.                                      |
| attribute list                         |                                                    |
+----------------------------------------+----------------------------------------------------+
| Dimension *a dimension* is not a       | This might happen when model was constructed       |
| subclass of Dimension class            | programatically. Check your model construction     |
|                                        | code.                                              |
+----------------------------------------+----------------------------------------------------+


Warnings
--------

+----------------------------------------+----------------------------------------------------+
| Warning                                | Resolution                                         |
+========================================+====================================================+
| No fact specified for cube *a cube*    | Specify a fact table/dataset, otherwise table with |
| (factless cubes are not yet supported, | name ``fact`` will be used. View builder will fail |
| using 'fact'  as default dataset/table | if such table does not exist.                      |
| name                                   |                                                    |
+----------------------------------------+----------------------------------------------------+
| No mapping for dimension *a dimension* | Provide mapping for dimension, otherwise identity  |
| attribute *an attribute* in cube       | mapping will be used (``dimension.attribute``)     |
| *a cube* (using default mapping)       |                                                    |
+----------------------------------------+----------------------------------------------------+
| No default hierarchy name specified in | Provide ``default_hierarchy_name``. If there is    |
| dimension *a dimension*, using         | only one hierarchy for dimension, the only one     |
| *some autodetect default name*         | will be used. If there are more hierarchies,       |
|                                        | the one with name ``default`` will be used.        |
+----------------------------------------+----------------------------------------------------+
| Default hierarchy *a hierarchy* does   | Check that ``default_hierarchy`` refers to existing|
| not exist in dimension *a dimension*   | hierarchy within that dimension.                   |
+----------------------------------------+----------------------------------------------------+
| Level *a level* in dimension           |  Specify ``key`` attribute in the dimension level. |
| *a dimension* has no key attribute     |                                                    |
| specified, first attribute will        |                                                    |
| be used: *first attribute name*        |                                                    |
+----------------------------------------+----------------------------------------------------+
| No cubes defined                       | Define at least one cube.                          |
+----------------------------------------+----------------------------------------------------+
