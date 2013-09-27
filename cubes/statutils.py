from collections import deque
from cubes.model import Attribute
from cubes.browser import SPLIT_DIMENSION_NAME

__all__ = [
        "CALCULATED_AGGREGATIONS",
        "calculators_for_aggregates"
]

def calculators_for_aggregates(aggregates, drilldown_levels=None, split=None,
                               backend_functions=None):
    """Returns a list of calculator function objects that implements
    aggregations by calculating on retrieved results, given a particular
    drilldown. Only post-aggregation calculators are returned.

    Might return an empty list if there is no post-aggregation witin
    aggregate functions.

    `backend_functions` is a list of backend-specific functions.
    """
    backend_functions = backend_functions or []

    # If we have an aggregation function, then we consider the aggregate
    # already processed
    functions = []

    for aggregate in aggregates:
        # Ignore function if the backend already handles it
        if aggregate.function in backend_functions:
            continue

        try:
            func = CALCULATED_AGGREGATIONS[aggregate.function]
        except KeyError:
            raise ArgumentError("Unknown post-calculation function '%s' for "
                                "aggregate '%s'" % (aggregate.function,
                                                    aggregate.name))

        func = (measure, drilldown_levels, split, non_calculated_aggs)
        functions.append(func)

    return functions


def _wma(values):
    n = len(values)
    denom = n * (n + 1) / 2
    total = 0.0
    idx = 1
    for val in values:
        total += float(idx) * float(val)
        idx += 1
    return round(total / denom, 4)

def _sma(values):
    # use all the values
    return round(reduce(lambda i, c: float(c) + i, values, 0.0) / len(values), 2)

def weighted_moving_average_factory(measure, drilldown_paths, split_cell, source_aggregations):
    return _moving_average_factory(measure, drilldown_paths, split_cell, source_aggregations, _wma, 'wma')

def simple_moving_average_factory(measure, drilldown_paths, split_cell, source_aggregations):
    return _moving_average_factory(measure, drilldown_paths, split_cell, source_aggregations, _sma, 'sma')

def _moving_average_factory(measure, drilldown_paths, split_cell, source_aggregations, avg_func, aggregation_name):
    if not source_aggregations:
        return lambda item: None

    # if the level we're drilling to doesn't have aggregation_units configured,
    # we're not doing any calculations
    key_drilldown_paths = []

    num_units = None
    drilldown_paths = drilldown_paths or []
    for path in drilldown_paths:
        relevant_level = path.levels[-1]
        these_num_units = None
        if relevant_level.info:
            these_num_units = relevant_level.info.get('aggregation_units', None)
        if these_num_units is None:
            key_drilldown_paths.append(path)
        else:
            num_units = these_num_units

    if num_units is None or not isinstance(num_units, int) or num_units < 1:
        num_units = 1

    # if no key_drilldown_paths, the key is always the empty tuple.
    def key_extractor(item):
        vals = []
        if split_cell:
            vals.append( item.get(SPLIT_DIMENSION_NAME) )
        for dditem in key_drilldown_paths:
            for level in dditem.levels:
                vals.append( item.get(level.key.ref()) )
        return tuple(vals)

    calculators = []
    measure_baseref = measure.ref()

    for agg in source_aggregations:
        if agg != "identity":
            measure_ref = measure_baseref + "_" + agg
        else:
            measure_ref = measure_baseref
        calculators.append(
            _calc_func(measure_ref + "_" + aggregation_name, measure_ref, avg_func, key_extractor, num_units)
        )

    def calculator(item):
        for calc in calculators:
            calc(item)

    return calculator

def _calc_func(field_name, measure_ref, avg_func, key_extractor, num_units):

    by_value_map = {}
    def f(item):
        by_value = key_extractor(item)
        val_list = by_value_map.get(by_value)
        if val_list is None:
            val_list = deque()
            by_value_map[by_value] = val_list
        val = item.get(measure_ref)
        if val is not None:
            val_list.append(val)
        while len(val_list) > num_units:
            val_list.popleft()
        if len(val_list) > 0:
            item[field_name] = avg_func(val_list)

    return f


# TODO: make CALCULATED_AGGREGATIONS a namespace (see extensions.py)
CALCULATED_AGGREGATIONS = {
    "sma": simple_moving_average_factory,
    "wma": weighted_moving_average_factory
}

