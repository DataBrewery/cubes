# -*- encoding: utf-8 -*-

from __future__ import absolute_import

import itertools

from .errors import ArgumentError

__all__ = [
    "combined_cuboids",
    "combined_levels",
    "hierarchical_cuboids"
]

def combined_cuboids(dimensions, required=None):
    """Returns a list of all combinations of `dimensions` as tuples. For
    example, if `dimensions` is: ``['date', 'product']`` then it returns:

        ``[['date', 'cpv'], ['date'], ['cpv']]``
    """

    required = tuple(required) if required else ()

    for dim in required:
        if dim not in dimensions:
            raise ArgumentError("Required dimension '%s' is not in list of "
                                "dimensions to be combined." % str(dim))

    cuboids = []
    to_combine = [dim for dim in dimensions if not dim in required]

    for i in range(len(to_combine), 0, -1):
        combos = itertools.combinations(to_combine, i)
        combos = [required+combo for combo in combos]

        cuboids += tuple(combos)

    if required:
        cuboids = [required] + cuboids

    return cuboids

def combined_levels(dimensions, default_only=False):
    """Create a cartesian product of levels from all `dimensions`. For
    example, if dimensions are _date_, _product_ then result will be:
    levels of _date_ X levels of _product_. Each element of the returned list
    is a list of tuples (`dimension`, `level`)
    """
    groups = []
    for dim in dimensions:
        if default_only:
            levels = dim.hierarchy().levels
        else:
            levels = dim.levels

        group = [(str(dim), str(level)) for level in levels]
        groups.append(group)

    return tuple(itertools.product(*groups))


def hierarchical_cuboids(dimensions, required=None, default_only=False):
    """Returns a list of cuboids with all hierarchical level combinations."""
    cuboids = combined_cuboids(dimensions, required)

    result = []
    for cuboid in cuboids:
        result += list(combined_levels(cuboid, default_only))

    return result

