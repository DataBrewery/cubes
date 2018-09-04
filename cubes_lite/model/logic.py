# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from ..errors import ExpressionError


def collect_attributes(attributes, *containers):
    """Collect attributes from arguments. `containers` are objects with
    method `all_attributes` or might be `Nulls`. Returns a list of attributes.
    Note that the function does not check whether the attribute is an actual
    attribute object or a string."""
    # Method for decreasing noise/boilerplate

    collected = []

    if attributes:
        collected += attributes

    for container in containers:
        if container:
            collected += container.all_attributes

    return collected


def depsort_attributes(attributes, all_dependencies):
    """Returns a sorted list of attributes by their dependencies. `attributes`
    is a list of attribute names, `all_dependencies` is a dictionary where keys
    are attribute names and values are direct attribute dependencies (that is
    attributes in attribute's expression, for example). `all_dependencies`
    should contain all known attributes, variables and constants.

    Raises an exception when a circular dependecy is detected."""

    bases = set()

    # Gather only relevant dependencies
    required = set(attributes)

    # Collect base attributes and relevant dependencies
    seen = set()
    while required:
        attr = required.pop()
        seen.add(attr)

        try:
            attr_deps = all_dependencies[attr]
        except KeyError as e:
            raise ExpressionError('Unknown attribute "{}"'.format(e))

        if not attr_deps:
            bases.add(attr)

        required |= set(attr_deps) - seen

    # Remaining dependencies to be processed (not base attributes)
    remaining = {
        attr: all_dependencies[attr]
        for attr in seen
        if attr not in bases
    }

    sorted_deps = []

    while bases:
        base = bases.pop()
        sorted_deps.append(base)

        dependants = [
            attr
            for attr, deps in remaining.items()
            if base in deps
        ]

        for attr in dependants:
            # Remove the current dependency
            remaining[attr].remove(base)
            # no more dependencies -> consider the attribute to be base
            if not remaining[attr]:
                bases.add(attr)
                del remaining[attr]

    if remaining:
        remaining_str = ', '.join(sorted(remaining))
        raise ExpressionError(
            'Circular attribute reference (remaining: {})'
            .format(remaining_str)
        )

    return sorted_deps
