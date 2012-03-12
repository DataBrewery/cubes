**************************
Logical Model and Metadata
**************************

Introduction
============

Logical model describes the data from user's or analyst's perspective: data how they are being
measured, aggregated and reported. Model is independent of physical implementation of data. This
physical independence makes it easier to focus on data instead on ways of how to get the data in
understandable form. Objects and functionality for working with metadata are provided by the :mod:`model` package.

In short, logical model enables users to:

* refer to dimension attributes by name regardless of storage (which table)
* specify hierarchical dependencies of attributes, such as:
    * `product category > product > subcategory > product`
    * `country > region > county > town`.
* specify attribute labels to be displayed in end-user application
* for all localizations use the same attribute name, therefore write only one 
  query for all report translations

Analysts or report writers do not have to know where name of an organisation or 
category is stored, nor he does not have to care whether customer data is 
stored in single table or spread across multiple tables (customer, customer 
types, ...). They just ask for `customer.name` or `category.code`.

In addition to abstraction over physical model, localization abstraction is 
included. When working in multi-lingual environment, only one version of 
report/query has to be written, locales can be switched as desired. If 
requesting "contract type name", analyst just writes `constract_type.name`
and Cubes framework takes care about appropriate localisation of the value.

Example: Analysts wants to report contract amounts by geography which has two 
levels: country level and region level. In original physical database, the 
geography information is normalised and stored in two separate tables, one for 
countries and another for regions. Analyst does not have to know where the data 
are stored, he just queries for `geography.country` and/or `geography.region` 
and will get the proper data. How it is done is depicted on the following image:

.. figure:: logical-to-physical.png
    :align: center
    :width: 500px

    Mapping from logical model to physical data.

The logical model describes dimensions `geography` in which default hierarchy 
has two levels: `country` and `region`. Each level can have more attributes, 
such as code, name, population... In our example report we are interested only 
in geographical names, that is: `country.name` and `region.name`.

How the physical attributes are located is described in the :doc:`mapping` 
chapter.

Logical Model description
=========================

The logical model can be either constructed programmatically or provided as JSON. The model entities and
their structure is depicted on the following figure:

.. figure:: logical_model.png
    :align: center
    :width: 550px

    The logical model entities and relationships.

Dimensions
----------

Dimension descriptions are stored in model dictionary under the key ``dimensions``.

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
hierarchy      if dimension has only one hierarchy, you can
               specify it hiere. 
============== ===================================================

Example::

    {
        "name": "date",
        "label": "Dátum",
        "levels": { ... }
        "attributes": [ ... ]
        "hierarchies": { ... }
    }

Use either ``hierarchies`` or ``hierarchy``, using both results in an error.

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

Attributes
----------

Measures and dimension level attributes can be specified either as rich metadata or just simply as
strings. If only string is specified, then all attribute metadata will have default values, label
will be equal to the attribute name.

================ ================================================================
Key              Description
================ ================================================================
name             attribute name, used in reports
label            human readable name - can be used in an application, localizable
order            natural order of the attribute (optional), can be ``asc`` or 
                 ``desc``
locales          list of locales in which the attribute values are available in
                 (optional)
================ ================================================================

The optional `order` is used in aggregation browsing and reporting. If specified, then all queries
will have results sorted by this field in specified direction. Level hierarchy is used to order
ordered attributes. Only one ordered attribute should be specified per dimension level, otherwise
the behaviour is unpredictable. This natural (or default) order can be later overriden in reports
by explicitly specified another ordering direction or attribute. Explicit order takes precedence
before natural order.

For example, you might want to specify that all dates should be ordered by default::

    "attributes" = [
        {"name" = "year", "order": "asc"}
    ]

Locales is a list of locale names. Say we have a `CPV` dimension (common procurement vocabulary -
EU procurement subject hierarchy) and we are reporting in Slovak, English and Hungarian. The
attributes will be therefore specified as::


    "attributes" = [
        {"name" = "group_code"},
        {"name" = "group_name", "order": "asc", "locales" = ["sk", "en", "hu"]}
    ]
    
`group name` is localized, but `group code` is not. Also you can see that the result will always
be sorted by `group name` alphabeticall in ascending order. See :ref:`PhysicalAttributeMappings`
for more information about how logical attributes are mapped to the physical sources.

In reports you do not specify locale for each locaized attribute, you specify locale for whole
report or browsing session. Report queries remain the same for all languages.

Model validation
================

To validate a model do::

    results = model.validate()
    
This will return a list of tuples `(result, message)` where result might be 
'warning' or 'error'. If validation contains errors, the model can not be used 
without resulting in failure. If there are warnings, some functionalities might 
or might not fail or might not work as expected.

You can validate model from command line::

    slicer model validate /path/to/model
    
See :doc:`slicer` for more information about the tool.

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
