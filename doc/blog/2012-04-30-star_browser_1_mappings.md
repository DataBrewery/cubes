Star Browser, Part 1: Mappings
==============================

Star Browser is new aggregation browser in for the
[Cubes](https://github.com/Stiivi/cubes) – lightweight Python OLAP Framework.
I am going to talk briefly about current state and why new browser is needed.
Then I will describe in more details the new browser: how mappings work, how
tables are joined. At the end I will mention what will be added soon and what
is planned in the future.

Originally I wanted to write one blog post about this, but it was too long, so
I am going to split it into three:

* mappings (this one)
* joins and denormalization
* aggregations and new features

Why new browser?
================

Current [denormalized
browser](https://github.com/Stiivi/cubes/blob/master/cubes/backends/sql/browser.py)
is good, but not good enough. Firstly, it has grown into a spaghetti-like
structure inside and adding new features is quite difficult. Secondly, it is
not immediately clear what is going on inside and not only new users are
getting into troubles. For example the mapping of logical to physical is not
obvious; denormalization is forced to be used, which is good at the end, but
is making OLAP newbies puzzled.

The new browser, called
[StarBrowser](https://github.com/Stiivi/cubes/blob/master/cubes/backends/sql/star.py).
is half-ready and will fix many of the old decisions with better ones.

Mapping
=======

Cubes provides an analyst's view of dimensions and their attributes by hiding
the physical representation of data. One of the most important parts of proper
OLAP on top of the relational database is the mapping of physical attributes
to logical.

First thing that was implemented in the new browser is proper mapping of
logical attributes to physical table columns. For example, take a reference to
an attribute *name* in a dimension *product*. What is the column of what table
in which schema that contains the value of this dimension attribute?

![](http://media.tumblr.com/tumblr_m3ajdppDAa1qgmvbu.png)

There are two ways how the mapping is being done: implicit and explicit. The
simplest, straightforward and most customizable is the explicit way, where the
actual column reference is provided in the model description:

<pre class="prettyprint">
"mappings": {
    "product.name": "dm_products.product_name"
}
</pre>

If it is in different schema or any part of the reference contains a dot:

<pre class="prettyprint">
"mappings": {
    "product.name": {
            "schema": "sales",
            "table": "dm_products",
            "column": "product_name"
        }
}
</pre>

Disadvantage of the explicit way is it's verbosity and the fact that developer
has to write more metadata, obviously.

Both, explicit and implicit mappings have ability to specify default database
schema (if you are using Oracle, PostgreSQL or any other DB which supports
schemas).

The mapping process process is like this:

![](http://media.tumblr.com/tumblr_m3akrsmX9b1qgmvbu.png)

Implicit Mapping
----------------

With implicit mapping one can match a database schema with logical model and
does not have to specify additional mapping metadata. Expected structure is
star schema with one table per (denormalized) dimension.

Basic rules:

* fact table should have same name as represented cube
* dimension table should have same name as the represented dimension, for
  example: `product` (singular)
* references without dimension name in them are expected to be in the fact
  table, for example: `amount`, `discount` (see note below for simple flat
  dimensions)
* column name should have same name as dimension attribute: `name`, `code`,
  `description`
* if attribute is localized, then there should be one column per localization
  and should have locale suffix: `description_en`, `description_sk`,
  `description_fr` (see below for more information)
  
This means, that by default `product.name` is mapped to the table `product`
and column `name`. Measure `amount` is mapped to the table `sales` and column
`amount`

What about dimensions that have only one attribute, like one would not have a
full date but just a `year`? In this case it is kept in the fact table without
need of separate dimension table. The attribute is treated in by the same rule
as measure and is referenced by simple `year`. This is applied to all
dimensions that have only one attribute (representing key as well). This
dimension is referred to as *flat and without details*.

Note for advanced users: this behavior can be disabled by setting
`simplify_dimension_references` to `False` in the mapper. In that case you
will have to have separate table for the dimension attribute and you will have
to reference the attribute by full name. This might be useful when you know
that your dimension will be more detailed.

Localization
------------

Despite localization taking place first in the mapping process, we talk about
it at the end, as it might be not so commonly used feature. From physical
point of view, the data localization is very trivial and requires language
denormalization - that means that each language has to have its own column for
each attribute.

In the logical model, some of the attributes may contain list of locales that
are provided for the attribute. For example product category can be in
English, Slovak or German. It is specified in the model like this:

<pre class="prettyprint">
attributes = [{
    "name" = "category",
    "locales" = [en, sk, de],
}]
</pre>

During the mapping process, localized logical reference is created first:

![](http://media.tumblr.com/tumblr_m3aksf89Zb1qgmvbu.png)

In short: if attribute is localizable and locale is requested, then locale
suffix is added. If no such localization exists then default locale is used.
Nothing happens to non-localizable attributes.

For such attribute, three columns should exist in the physical model. There
are two ways how the columns should be named. They should have attribute name
with locale suffix such as `category_sk` and `category_en` (_underscore_
because it is more common in table column names), if implicit mapping is used.
You can name the columns as you like, but you have to provide explicit mapping
in the mapping dictionary. The key for the localized logical attribute should
have `.locale` suffix, such as `product.category.sk` for Slovak version of
category attribute of dimension product. Here the _dot_ is used because dots
separate logical reference parts.

Customization of the Implicit
-----------------------------

The implicit mapping process has a little bit of customization as well:

* *dimension table prefix*: you can specify what prefix will be used for all
  dimension tables. For example if the prefix is `dim_` and attribute is
  `product.name` then the table is going to be `dim_product`.
* *fact table prefix*: used for constructing fact table name from cube name.
  Example: having prefix `ft_` all fact attributes of cube `sales` are going
  to be looked up in table `ft_sales`
* *fact table name*: one can explicitly specify fact table name for each cube
  separately

The Big Picture
===============

Here is the whole mapping schema, after localization:

![](http://media.tumblr.com/tumblr_m3akttdCmK1qgmvbu.png)

Links
=====

The commented mapper source is
[here](https://github.com/Stiivi/cubes/blob/master/cubes/backends/sql/common.py).

* [github sources](https://github.com/Stiivi/cubes)
* [Documentation](http://packages.python.org/cubes/)
* [Mailing List](http://groups.google.com/group/cubes-discuss/)
* [Submit issues](https://github.com/Stiivi/cubes/issues)
* IRC channel [#databrewery](irc://irc.freenode.net/#databrewery) on irc.freenode.net
