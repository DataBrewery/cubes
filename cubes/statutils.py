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
    return _moving_average_factory(measure, drilldown_paths, _wma, 'wma')

def simple_moving_average_factory(measure, drilldown_paths):
    return _moving_average_factory(measure, drilldown_paths, _sma, 'sma')

def _moving_average_factory(measure, drilldown_paths, avg_func, aggregation_name):
    if not drilldown_paths:
        return lambda item: None

    # if the level we're drilling to doesn't have aggregation_units configured,
    # we're not doing any calculations
    key_drilldown_paths = []
    num_units = None
    for path in drilldown_paths:
        relevant_level = path[2][-1]
        these_num_units = None
        if relevant_level.info:
            these_num_units = relevant_level.info.get('aggregation_units', None)
        if these_num_units is None:
            key_drilldown_paths.append(path)
        else:
            num_units = these_num_units

    if num_units is None or not isinstance(num_units, int) or num_units < 2:
        return lambda item: None

    # determine the measure on which to calculate.
    measure_ref = measure.ref()
    for agg in measure.aggregations:
        if agg == aggregation_name:
            continue
        if agg != "identity":
            measure_ref += "_" + agg
        break

    field_name = measure_ref + '_' + aggregation_name

    # if no key_drilldown_paths, the key is always the empty tuple.
    def key_extractor(item):
        vals = []
        for dim, hier, levels in key_drilldown_paths:
            for level in levels:
                vals.append( item.get(level.key.ref()) )
        return tuple(vals)


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

