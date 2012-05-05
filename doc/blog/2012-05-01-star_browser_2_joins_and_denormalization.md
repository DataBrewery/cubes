Last time I was talking about how [logical attributes are mapped to the
physical table columns](http://blog.databrewery.org/post/22119118550) in the
Star Browser. Today I will describe how joins are formed and how
denormalization is going to be used.

The Star Browser is new aggregation browser in for the
[Cubes](https://github.com/Stiivi/cubes) – lightweight Python OLAP Framework.

Star, Snowflake, Master and Detail
=================================

Star browser supports a star:

![](http://media.tumblr.com/tumblr_m3ajfbXcHo1qgmvbu.png)

... and snowflake database schema:

![](http://media.tumblr.com/tumblr_m3ajfn8QYt1qgmvbu.png)

The browser should know how to construct the star/snowflake and that is why
you have to specify the joins of the schema. The join specification is very
simple: 

<pre class="prettyprint">
"joins" = [
    { "master": "fact_sales.product_id", "detail": "dim_product.id" }
]
</pre>    

Joins support only single-column keys, therefore you might have to create
surrogate keys for your dimensions.

As in mappings, if you have specific needs for explicitly mentioning database
schema or any other reason where `table.column` reference is not enough, you
might write:

<pre class="prettyprint">
"joins" = [
    { 
        "master": "fact_sales.product_id",
        "detail": {
            "schema": "sales",
            "table": "dim_products",
            "column": "id"
        }
]
</pre>

What if you need to join same table twice? For example, you have list of
organizations and you want to use it as both: supplier and service consumer.
It can be done by specifying alias in the joins:

<pre class="prettyprint">
"joins" = [
    {
        "master": "contracts.supplier_id", 
        "detail": "organisations.id",
        "alias": "suppliers"
    },
    {
        "master": "contracts.consumer_id", 
        "detail": "organisations.id",
        "alias": "consumers"
    }
]
</pre>

In the mappings you refer to the table by alias specified in the joins, not by
real table name:

<pre class="prettyprint">
"mappings": {
    "supplier.name": "suppliers.org_name",
    "consumer.name": "consumers.org_name"
}
</pre>

![](http://media.tumblr.com/tumblr_m3ajian3sA1qgmvbu.png)

Relevant Joins and Denormalization
----------------------------------

The new mapper joins only tables that are relevant for given query. That is,
if you are browsing by only one dimension, say *product*, then only product
dimension table is joined.

Joins are slow, expensive and the denormalization can be
helpful:

![](http://media.tumblr.com/tumblr_m3ajglKwV11qgmvbu.png)

The old browser is based purely on the denormalized view. Despite having a
performance gain, it has several disadvantages. From the
join/performance perspective the major one is, that the denormalization is
required and it is not possible to browse data in a database that was
"read-only". This requirements was also one unnecessary step for beginners,
which can be considered as usability problem.

Current implementation of the *Mapper* and *StarBrowser* allows
denormalization to be integrated in a way, that it might be used based on
needs and situation:

![](http://media.tumblr.com/tumblr_m3d4ctMm6K1qgmvbu.png)

It is not yet there and this is what needs to be done:

* function for denormalization - similar to the old one: will take cube and
  view name and will create denormalized view (or a table)
* make mapper accept the view and ignore joins

Goal is not just to slap denormalization in, but to make it a configurable
alternative to default star browsing. From user's perspective, the workflow
will be:

1. browse star/snowflake until need for denormalization arises
2. configure denormalization and create denormalized view
3. browse the denormalized view

The proposed options are: `use_denormalization`, `denormalized_view_prefix`,
`denormalized_view_schema`.

The Star Browser is half-ready for the denormalization, just few changes are
needed in the mapper and maybe query builder. These changes have to be
compatible with another, not-yet-included feature: SQL pre-aggregation.

Conclusion
==========

The new way of joining is very similar to the old one, but has much more
cleaner code and is separated from mappings. Also it is more transparent. New
feature is the ability to specify a database schema. Planned feature to be
integrated is automatic join detection based on foreign keys.

In the next post, the last post about the new *StarBrowser*, you are going to
learn about aggregation improvements and changes.

Links
=====

Relevant source code is [this one] (https://github.com/Stiivi/cubes/blob/master/cubes/backends/sql/common.py) (github).

See also [Cubes at github](https://github.com/Stiivi/cubes),
[Cubes Documentation](http://packages.python.org/cubes/),
[Mailing List](http://groups.google.com/group/cubes-discuss/)
and [Submit issues](https://github.com/Stiivi/cubes/issues). Also there is an 
IRC channel [#databrewery](irc://irc.freenode.net/#databrewery) on
irc.freenode.net
