***************
MongoDB Backend
***************

Requirements: `pymongo`::

    pip install pymongo

Store Configuration
===================

Type is ``mongo2``

* ``url`` – Mongo database URL, for example ``mongodb://localhost:37017/`` 
* ``database`` – name of the Mongo database
* ``collection`` – name of mongo collection where documents are facts

Example::

    [datastore]
    type: mongo2
    url: mongodb://localhost:37017/
    database: MongoBI
    collection: activations

Mappings
========

Custom aggregate with function provided in the mapping:

.. code-block:: javascript

    "aggregates": [
        {
            "name": "subtotal",
        }
    ],
    "mappings": {
        "subtotas": {
            "field": "cart_subtotal",
            "group": { "$sum": "$subtotal" }
        }
    }

Collection Filter
=================

To apply a filter for the whole collection:

.. code-block:: javascript

    "browser_options": {
        "filter": {
            "type": "only_this_type",
            "category": 1
        }
    }
