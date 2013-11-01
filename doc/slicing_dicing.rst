##################
Slicing and Dicing
##################

Aggregate
=========

* `aggregate()`

Cell and Cuts
-------------

* `aggregate(cell)`

* point cut
* set cut
* range cut

Drilldown
---------

* `aggregate(cell, drilldown)`
* `aggregate(cell, aggregates, drilldown)`
* `aggregate(cell, drilldown, page, page_size)`

* ``dim``
* ``dim:level``
* ``dim@hierarchy:level``

Split
-----

Provisional:

* `aggregate(cell, drilldown, split)`


Facts
=====

* `facts()`
* `facts(cell)`
* `facts(cell, fields)`

Fact
====

* `fact(id)`

Members
=======

* `members(cell, dimension)`
* `members(cell, dimension, depth)`
* `members(cell, dimension, depth, hierarchy)`

Cell Details
============

When we are browsing a cube, the cell provides current browsing context. For
aggregations and selections to happen, only keys and some other internal
attributes are necessary. Those can not be presented to the user though. For
example we have geography path (`country`, `region`) as ``['sk', 'ba']``,
however we want to display to the user `Slovakia` for the country and
`Bratislava` for the region. We need to fetch those values from the data
store.  Cell details is basically a human readable description of the current
cell.

For applications where it is possible to store state between aggregation
calls, we can use values from previous aggregations or value listings. Problem
is with web applications - sometimes it is not desirable or possible to store
whole browsing context with all details. This is exact the situation where
fetching cell details explicitly might come handy.

The cell details are provided by method
:func:`cubes.AggregationBrowser.cell_details()` which has Slicer HTTP
equivalent ``/cell`` or ``{"query":"detail", ...}`` in ``/report`` request
(see the :doc:`server documentation<server>` for more information).

For point cuts, the detail is a list of dictionaries for each level. For
example our previously mentioned path ``['sk', 'ba']`` would have details
described as:

.. code-block:: javascript

    [
        {
            "geography.country_code": "sk",
            "geography.country_name": "Slovakia",
            "geography.something_more": "..."
            "_key": "sk",
            "_label": "Slovakia"
        },
        {
            "geography.region_code": "ba",
            "geography.region_name": "Bratislava",
            "geography.something_even_more": "...",
            "_key": "ba",
            "_label": "Bratislava"
        }
    ]
    
You might have noticed the two redundant keys: `_key` and `_label` - those
contain values of a level key attribute and level label attribute
respectively. It is there to simplify the use of the details in presentation
layer, such as templates. Take for example doing only one-dimensional
browsing and compare presentation of "breadcrumbs":

.. code-block:: python

    labels = [detail["_label"] for detail in cut_details]

Which is equivalent to:

.. code-block:: python

    levels = dimension.hierarchy().levels()
    labels = []
    for i, detail in enumerate(cut_details):
        labels.append(detail[level[i].label_attribute.ref()])

Note that this might change a bit: either full detail will be returned or just
key and label, depending on an option argument (not yet decided).

