from itertools import groupby

def _median_on_distribution(l):
    """ Returns median on distribution

    >>> _median_on_distribution([(1, 5), (2, 10), (5, 1), (7, 3), (11, 2)])
    2
    >>> _median_on_distribution([(1, 5), (2, 10), (5, 8), (7, 3), (11, 6)])
    5
    >>> _median_on_distribution([(1, 5), (2, 10), (5, 8), (7, 7)])
    3.5
    >>> _median_on_distribution([(1, 5), (7, 3), (5, 8), (11, 6), (2, 10)])
    5
    """
    l.sort(key=lambda e: e[0])
    head = tail = 0
    hi, ti = 0, len(l)-1
    while True:
        if hi > ti:
            if head > tail:
                return l[hi-1][0]
            elif tail > head:
                return l[ti+1][0]
            else:
                return float(l[hi][0] + l[ti][0])/2
        if head > tail:
            tail += l[ti][1]
            ti -= 1
        else:
            head += l[hi][1]
            hi += 1

def _extract_tuples( list_of_dicts, tuple_of_attrs):
    """

    Args:
        list_of_dicts:
        tuple_of_attrs:

    Returns: list of tuples, taken from dict by keys stored in tuple_of_dicts

    >>> l = [{'a':1, 'b':2, 'c':3}, {'a':101, 'b': 102, 'c': 103}]
    >>> _extract_tuples(l, ['a', 'c'])
    [(1, 3), (101, 103)]
    """
    result = []
    for d in list_of_dicts:
        elem = []
        for a in tuple_of_attrs:
            elem.append(d[a])
        result.append(tuple(elem))
    return result

def median(result, measure, target):
    measures = measure.split(',')
    drilldowns = [d.dimension.name for d in result.drilldown]
    group_keys = [k for k in drilldowns if not k in measures]
    def group_key(elem):
        key = []
        for k in group_keys:
            key.append(elem[k])
        return tuple(key)
    value, count = measures

    grouped_cells = groupby(
        sorted(result.cells, key=group_key),
        key=group_key)

    result._cells = []
    for g in grouped_cells:
        cell = dict(zip(group_keys, g[0]))
        cell[target] = _median_on_distribution(_extract_tuples(g[1], (value, count)))
        result._cells.append(cell)





