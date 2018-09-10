# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from ..errors import ModelError


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
            raise ModelError('Unknown attribute "{}"'.format(e))

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
        raise ModelError(
            'Circular attribute reference (remaining: {})'
            .format(remaining_str)
        )

    return sorted_deps
