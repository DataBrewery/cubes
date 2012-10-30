import itertools

__all__ = [
        "combined_cuboids",
        "combined_levels",
        "hierarchical_cuboids"
        ]

def combined_cuboids(dimensions):
    """Returns a list of all combinations of `dimensions` as tuples. For
    example, if `dimensions` is: ``['date', 'product']`` then it returs::

        ``[['date', 'cpv'], ['date'], ['cpv']]``
    """
    cuboids = []
    for i in range(len(dimensions), 0, -1):
        cuboids += tuple(itertools.combinations(dimensions, i))
    return cuboids

def combined_levels(dimensions):
    """Create a cartesian product of levels from all `dimensions`. For
    example, if dimensions are _date_, _product_ then result will be:
    levels of _date_ X levels of _product_. Each element of the returned list
    is a list of tuples (`dimension`, `level`)
    """
    groups = []
    for dim in dimensions:
        group = [(str(dim), str(level)) for level in dim.levels]
        groups.append(group)
    return tuple(itertools.product(*groups))


def hierarchical_cuboids(dimensions):
    """Returns a list of cuboids with all hierarchical level combinations."""
    cuboids = combined_cuboids(dimensions)

    result = []
    for cuboid in cuboids:
        result += list(combined_levels(cuboid))

    return result

