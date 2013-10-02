# -*- coding: utf-8 -*-
import bson

def to_json_safe(item):
    """Appropriates the `item` to be safely dumped as JSON."""
    result = {}
    for key, value in item.items():
        if isinstance(value, bson.objectid.ObjectId):
            result[key] = str(value)
        else:
            result[key] = value

    return result

def collapse_record(record, separator = '.', root=None):
    """Collapses the `record` dictionary. If a value is a dictionary, then its
    keys are merged with the higher level dictionary.

    Example::

        {
            "date": {
                "year": 2013,
                "month" 10,
                "day": 1
            }
        }

    Will become::

        {
            "date.year": 2013,
            "date.month" 10,
            "date.day": 1
        }
    """

    result = {}
    for key, value in list(record.items()):
        if root:
            collapsed_key = root + separator + key
        else:
            collapsed_key = key

        if type(value) == dict:
            collapsed = collapse_record(value, separator, collapsed_key)
            result.update(collapsed)
        else:
            result[collapsed_key] = value

    return result


