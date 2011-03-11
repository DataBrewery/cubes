Introduction
++++++++++++

*Focus on data analysis, not on physical data structure*

Cubes is a framework for:

* Online Analytical Processing - OLAP, mostly relational DB based - ROLAP
* multidimensional analysis
* star and snowflake schema denormalisation
* cube comptutation (see :doc:`computing`)

Features:

* :doc:`model` - description of how data are being analysed and reported, independent of physical
  data implementation
* hierarchical dimensions (attrobites that have hierarchical dependencies, such as
  category-subcategory or country-region)
* localizable metadata and data :doc:`localization`

Framework has modular nature and supports multiple database backends, different ways of cube computation
and ways of browsing aggregated data.

* relational databases with SQL through SQL alchemy
* document based database in MongoDB

