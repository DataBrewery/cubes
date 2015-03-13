# -*- encoding=utf -*-
"""
cubes.epressions
~~~~~~~~~~~~~~~~

Arithmetic expressions

"""

from __future__ import absolute_import
from expressions import inspect_variables
from .errors import ModelError, ExpressionError

def attribute_dependencies(attribute):
    """Return a set of attributes that the `attribute` depends on."""
    if not attribute.expression:
        return set()

    return inspect_variables(attribute.expression)

def sorted_attributes(attributes):
    """Return list of attributes in their expression dependency order - from
    based to derived. Raises an exception when a circular dependecy is detected."""
    all_deps = {attr.name:attribute_dependencies(attr) for attr in attributes}
    attribute_map = {attr.name:attr for attr in attributes}

    bases = set()
    all_used = set()

    for attr, deps in list(all_deps.items()):
        if not deps:
            bases.add(attr)
            del all_deps[attr]
        all_used |= deps

    missing = all_used - set(attribute_map.keys())
    if missing:
        missing = sorted(list(missing))
        raise ExpressionError("Unknown attributes: {}"
                              .format(", ".join(missing)))

    sorted_deps = []

    while bases:
        base = bases.pop()
        sorted_deps.append(base)

        dependants = [attr for attr, deps in all_deps.items() if base in deps]

        for attr in dependants:
            # Remove the current dependency
            all_deps[attr].remove(base)
            # If there are no more dependencies, consider the attribute to be
            # base
            if not all_deps[attr]:
                bases.add(attr)
                del all_deps[attr]

    if all_deps:
        raise ExpressionError("Circular reference")

    return [attribute_map[name] for name in sorted_deps]

