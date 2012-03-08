+++++++++++++++++++++++++++++++++
Logical to Physical Model Mapping
+++++++++++++++++++++++++++++++++

.. note::

    This chapter relates mostly to the relational database backend (SQL)
    
Cubes framework has to know where those logical (reported) attributes are 
physically stored. First it needs to know which tables are related to the cube 
and then in which of the tables the attribute is represented as a column.

The process is done in two steps:

1. joining all star/snowflake tables
2. mapping logical attribute to table + column

Joins
=====

If you are using star or snowflake schema in relational database, Cubes 
requires information on how to join the tables into the star/snowflake. Tables 
are joined by matching single-column keys. The framewok needs to know how to
make this snowflake:

.. figure:: images/snowflake_schema.png
    :align: center
    :width: 400px

appear to the end-user as this (denormalized table) with attributes named by 
their logical name:

.. figure:: images/denormalized_schema.png
    :align: center
    :width: 400px

Join
----

The single join description consists of reference to the `master` table and a 
table with `details`. Fact table is example of master table, dimension is 
example of a detail table (in star schema).

The values for `master` and `detail` keys are references tables with to key 
columns in the form:

.. code-block:: javascript

    "joins" = [
        {
            "master": "fact_table.dimension_key",
            "detail": "dimension_table.dimension_key"
         }
    ]

For example, we have a fact table named ``fact_contracts`` and dimension table 
with categories named ``dm_categories``. To join them we define following join 
specification:

.. code-block:: javascript

    "joins" = [
        {
            "master": "fact_contracts.category_id",
            "detail": "dm_categories.id"
         }
    ]

Aliases
-------

There might be situations when you would need to join one detail table more 
than once. Example of such situation is a dimension with list of organisations 
and in fact table you have two organisational references, such as `receiver` 
and `donor`. In this case you specify alias for detail table:

.. code-block:: javascript

    "joins" = [
        {
            "master": "fact_contracts.receiver_id",
            "detail": "dm_organisation.id",
            "alias": "dm_receiver"
        }
        {
            "master": "fact_contracts.donor_id",
            "detail": "dm_organisation.id",
            "alias": "dm_donor"
        }
    ]

Note that order of joins matters, if you have snowflake and would like to join 
deeper detail, then you have to have all required tables joined (and properly 
aliased, if necessary) already.

In mappings you refer to table aliases, if you joined with an alias.

.. _PhysicalMapping:

Physical Mapping
================

End-user refers to attributes from the logical model. Cubes needs to know what 
real – physical – attributes contain the data for the corresponding logical 
ones.

For example in relational database, if we ask for `product.category_key` we 
need to know what table the attribute is stored, and how the table is joined to 
the fact table.

The mapping description in the model:

============== ===================================================
Key            Description
============== ===================================================
``fact``       name of a fact table (or collection or dataset, depending on backend)
``mappings``   dictionary of mapping of logical attribute to physical attribute
``joins``      list of join specifications
============== ===================================================


.. _PhysicalAttributeMappings:

Attribute Mappings
------------------

Mappings is a dictionary of logical attributes as keys and physical attributes 
(columns, fields) as values. The logical attributes references look like:

* `dimensions_name.attribute_name`, for example: ``geography.country_name`` or 
  ``category.code``
* `fact_attribute_name`, for example: ``amount`` or ``discount``

The physical attributes are backend-specific, for example in relational 
database (SQL) it can be ``table_name.column_name``.

If there is no mapping for a logical attribute specified, then default mapping 
is used - physical attribute is the same as logical attribute. For example, if 
you have dimension `category` and have attribute `code` (referenced as 
``category.code``) then Cubes looks in table named `category` and column `code`.

.. note::

    There is an exception for flat dimensions - dimensions without levels nor 
    details, dimensions that are represented just by one attribute. In the case
    of such kind of dimension only dimension name is used. Therefore if you have
    dimension named `flag` then the logical reference would be just ``flag``.
    
    This will be implemented more consistently and with an configurable option 
    int the future version of SQL browser.

Localized Attributes
--------------------

Localizable attributes are those attributes that have ``locales`` specified in 
their definition. To map logical attributes which are localizable, use locale 
suffix for each locale. For example attribute `name` in dimension `category` 
has two locales: Slovak (``sk``) and English (``en``), the mapping for such 
attribute will look like:

.. code-block:: javascript

    ...
        "category.name.sk" = "dm_categories.name_sk",
        "category.name.en" = "dm_categories.name_en",
    ...
    
.. note::

    Current implementation of Cubes framework requires a star or snowflake 
    schema that can be joined into fully denormalized normalized form. 
    Therefore all localized attributes have to be stored in their own columns. 
    You have to denormalize the data before using them in Cubes.

Read more about :doc:`localization`.

Future
======

.. warning::

    Following algorithm is from the new star browser in SQL backend. It can not 
    be used yet, however the diagram is here because it is very close to the 
    current implementation of the SQL backend (in fact it is fixed version of 
    the current).

Following diagram describes how the mapping of logical to physical attributes 
is done in the new star SQL browser (see 
:class:`cubes.backends.sql.StarBrowser`):

.. figure:: images/mapping-logical_to_physical.png
    :align: center
    :width: 600px

    logical to physical attribute mapping

The "red path" shows the most common scenario where defaults are used.
