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
    """Return a set of attributes that the `attribute` depends on. If the
    `attribute` is an expresion, then returns the direct dependencies from the
    expression. If the attribute is an aggregate with an unary function
    operating on a measure, then the measure is considered as a dependency.
    Attribute can't have both expression and measure specified, since you can
    have only expression or an function, not both.
    """

    if hasattr(attribute, "measure") and attribute.measure:
        if attribute.expression:
            raise ModelError("Aggregate '{}' has both measure and "
                             "expression set".format(attribute.ref()))
        return set([attribute.measure])

    if not attribute.expression:
        return set()

    return inspect_variables(attribute.expression)

def depsort_attributes(attributes, all_dependencies):
    """Returns a sorted list of attributes by their dependencies. `attributes`
    is a list of attribute names, `all_dependencies` is a dictionary where keys
    are attribute names and values are direct attribute dependencies (that is
    attributes in attribute's expression, for example). `all_dependencies`
    should contain all known attributes, variables and constants.

    Raises an exception when a circular dependecy is detected."""

    bases = set()
    all_used = set()

    # Gather only relevant dependencies
    dependencies = {}
    required = set(attributes)

    # Collect base attributes and relevant dependencies
    seen = set()
    while(required):
        attr = required.pop()
        seen.add(attr)

        try:
            attr_deps = all_dependencies[attr]
        except KeyError as e:
            raise ExpressionError("Unknown attribute '{}'".format(e))

        if not attr_deps:
            bases.add(attr)

        required |= set(attr_deps) - seen

    # Remaining dependencies to be processed (not base attributes)
    remaining = {attr:all_dependencies[attr] for attr in seen
                 if attr not in bases}

    sorted_deps = []

    while bases:
        base = bases.pop()
        sorted_deps.append(base)

        dependants = [attr for attr, deps in remaining.items()
                           if base in deps]

        for attr in dependants:
            # Remove the current dependency
            remaining[attr].remove(base)
            # If there are no more dependencies, consider the attribute to be
            # base
            if not remaining[attr]:
                bases.add(attr)
                del remaining[attr]

    if remaining:
        remaining_str = ", ".join(sorted(remaining.keys()))
        raise ExpressionError("Circular attribute reference (remaining: {})"
                              .format(remaining_str))

    return sorted_deps

    if all_deps:
        raise ExpressionError("Circular reference")

    return [attribute_map[name] for name in sorted_deps]

