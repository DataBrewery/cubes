from collections import deque

def decorate_with_moving_averages(aggregration_result, cube):

    # determine the dimension used for time series, and its level.

    # determine the drilldown, and construct a function to extract an aggregation key.

    # determine the number of trailing units.

    # determine the type of average, and select the factory function.

    # determine the field name for the computed average.

    # If result items are absent or there is insufficient number of items, return.
    if ( len(avgs_data) < 2 ) or ( len(by_clause_values) > 0 and len(avgs_data) < len(by_clause_values) * 2 ):
        return None

    # call factory function with number of units, key extractor function; get the average generator.

    # walk through the data series, decorating each item if avg func returns not None.
    # be sure to iterate in the correct direction.
    avgs_data = []
    by_clause_values = set()
    for item in results.data:
        val = avg_func(item, mart_query.by_clause)
        if val is not None:
            if mart_query.by_clause is not None:
                by_clause_values.add( item.get(mart_query.by_clause) )
            avg_item = item.copy()
            avg_item['total'] = val
            avgs_data.append(avg_item)
  
    return {
        'type': avg_type,
        'units': { 'amount': nunits, 'unit': unit_type },
        'data': avgs_data
    }

_UNITS_MAP = {
    'day': (7, 'day'),
    'day so far': (7, 'day'),
    'week': (4, 'week'),
    'week so far': (4, 'week'),
    'month': (6, 'month'),
    'month so far': (6, 'month'),
    'quarter': (4, 'quarter'),
    'quarter so far': (4, 'quarter')
}

def number_of_units_in_avg(mart_query, results):
    r = _UNITS_MAP.get(mart_query.over_clause, (None, None))
    # TODO clamp to LAST N units / const?
    return r

def _wma(values):
    n = len(values)
    denom = n * (n + 1) / 2
    total = 0.0
    idx = 1
    for val in values:
        total += float(idx) * float(val)
        idx += 1
    return total / denom

def _sma(values):
    # use all the values
    return reduce(lambda i, c: c + i, values, 0.0) / len(values)

def weighted_moving_average_factory(num_units):
    return _moving_average_factory(_wma, num_units)

def simple_moving_average_factory(num_units):
    return _moving_average_factory(_sma, num_units)

def _moving_average_factory(avg_func, num_units):
    by_value_map = {}

    def f(item, by_clause=None):
        by_value = ( item.get(by_clause) if by_clause is not None else '__dummy__' )
        val_list = by_value_map.get(by_value)
        if val_list is None:
            val_list = deque()
            by_value_map[by_value] = val_list
        val = item.get('total')
        if val is not None:
            val_list.append(val)
        while len(val_list) > num_units:
            val_list.popleft()
        if len(val_list) >= num_units:
            return avg_func(val_list)
        else:
            return None

    return f

def _test(inputs):
    vals = map(lambda c: { 'total': c }, inputs)
    wma = map(weighted_moving_average_factory(len(vals)/2), vals)
    sma = map(simple_moving_average_factory(len(vals)/2), vals)
    print vals
    print sma
    print wma

if __name__ == '__main__':
    _test([12, 13, 14, 15, 16, 20, 30])
