from collections import deque
from cubes.model import Attribute

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
    return round(reduce(lambda i, c: c + i, values, 0.0) / len(values), 2)

def weighted_moving_average_factory(measure, drilldown_paths):
    return _moving_average_factory(measure, drilldown_paths, _wma, '_wma')

def simple_moving_average_factory(measure, drilldown_paths):
    return _moving_average_factory(measure, drilldown_paths, _sma, '_sma')

def _moving_average_factory(measure, drilldown_paths, avg_func, field_suffix):
    if not drilldown_paths:
        return lambda item: None

    # if the level we're drilling to doesn't have aggregation_units configured,
    # we're not doing any calculations
    relevant_level = drilldown_paths[-1][2][-1]
    if not relevant_level.info:
        return lambda item: None
    num_units = relevant_level.info.get('aggregation_units', None)
    if num_units is None or not isinstance(num_units, int) or num_units < 2:
        return lambda item: None

    def key_extractor(item):
        vals = []
        for dim, hier, levels in drilldown_paths[:-1]:
            for level in levels:
                vals.append( item.get(level.key.ref()) )
        return tuple(vals)
    field_name = measure.ref() + field_suffix

    by_value_map = {}

    def f(item):
        by_value = key_extractor(item)
        val_list = by_value_map.get(by_value)
        if val_list is None:
            val_list = deque()
            by_value_map[by_value] = val_list
        val = item.get(measure.ref())
        if val is not None:
            val_list.append(val)
        while len(val_list) > num_units:
            val_list.popleft()
        if len(val_list) >= num_units:
            item[field_name] = avg_func(val_list)

    return f

