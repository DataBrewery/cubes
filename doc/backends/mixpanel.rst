****************
Mixpanel Backend
****************

The Mixpanel backends provides mixpanel events as cubes and event properties
as dimensions.

Features:

* two measure aggregates: `total` and `unique`
* two derived measure aggregates: `total_sma` and `unique_sma` (simple moving
  average)
* time dimension with two hierarchies:
    * `ymdh` (default): `year`, `month`, `day` and `hour`
    * `wdh`: `week`, `day` and `hour`
* aggregation at year or top level
* drill-down without the time dimension (approximation)
* list of facts

Store Configuration and Model
=============================

Type is ``mixpanel``

* ``api_key`` – your Mixpanel API key
* ``api_secret`` – Mixpanel API secret

To obtain your API key log-in to the Mixpanel, go to Account, then Projects –
you will see a list of key/secret pairs for your projects.

Example::

    [datastore]
    type: mixpanel
    api_key: 0123456789abcdef0123456789abcdef
    api_secret: 0123456789abcdef0123456789abcdef

Model
-----

Mixpanel backend generates the model on-the-fly. You have to specify that the
provider is ``mixpanel`` not the static model file itself:

.. code-block:: javascript

    {
        "name": "mixpanel",
        "provider": "mixpanel"
    }

Model Customization
-------------------

It is possible to customize various properties of a cube or a dimension. The
customizable properties are: `name`, `label`, `description`, `category` and
`info`.

For example to customize `search engine` dimension:

.. code-block:: javascript

    "dimensions": [
        {
            "name": "search_engine",
            "label": "Search Engine",
            "description": "The search engine a user came from"
        }
    ]

Limit the Dimensions
~~~~~~~~~~~~~~~~~~~~

The list of dimensions can be limited by using a browser option
``allowed_dimensions`` or ``denied_dimensions``:

Following will allow only one dimension:

.. code-block:: javascript

    "browser_options": {
        "allowed_dimensions": "search_engine" 
    }

The ``browser_options`` can be specified at the model level – applies to all
cubes, or just at a cube level – applies only to that cube.

Dimension names
~~~~~~~~~~~~~~~

By default dimension names are the same as property names. If a property name
contains a special character such as space or ``$`` it is replaced by a
underscore. To use a different, custom dimension name add the
dimension-to-property mapping:

.. code-block:: javascript

    "mappings": {
        "city": "$city",
        "initial_referrer": "$initial_referrer"
    }

And define the dimension in the model as above.

Built-in dimension models with simplifiend name and with labels:

* `initial_referrer`
* `initial_referring_domain`
* `search_engine`
* `keyword`
* `os`
* `browser`
* `referrer`
* `referring_domain`
* `country_code`
* `city`

Source: `Mixpanel Special or reserved properties`_.

.. _Mixpanel Special or reserved properties: https://mixpanel.com/docs/properties-or-segments/special-or-reserved-properties

Cube Names
~~~~~~~~~~

By default, cube names are the same as event names. To use a custom cube name
add a mapping for ``cube:CUBENAME``:

.. code-block:: json

    "mappings": {
        "cube:campaign_delivery": "$campaign_delivery"
    }

Example
=======

Create a ``slicer.ini``:

.. code-block:: ini

    [workspace]
    model: model.json

    [datastore]
    type: mixpanel
    api_key: YOUR_API_KEY
    api_secret: YOUR_API_SECRET

    [server]
    prettyprint: true

Create a ``model.json``:

.. code-block:: json

    {
        "provider": "mixpanel"
    }

Run the server:

.. code-block:: sh

    slicer serve slicer.ini

Get a list of cubes:

.. codeb-block:: sh

    curl "http://localhost:5000/cubes"

Notes
=====

.. important::

    It is not possible to specify a cut for the `time` dimension at the hour
    level. This is the Mixpanel's limitation – it expects the from-to range to
    be at day granularity.
