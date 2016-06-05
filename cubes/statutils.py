# -*- coding: utf-8 -*-

from collections import deque
from functools import partial
from math import sqrt

from .errors import ArgumentError, InternalError, ModelError
from . import compat

__all__ = [
    "CALCULATED_AGGREGATIONS",
    "calculators_for_aggregates",
    "available_calculators",
    "aggregate_calculator_labels"
]


def calculators_for_aggregates(cube, aggregates, drilldown_levels=None,
                               split=None):
    """Returns a list of calculator function objects that implements
    aggregations by calculating on retrieved results, given a particular
    drilldown. Only post-aggregation calculators are returned.

    Might return an empty list if there is no post-aggregation witin
    aggregate functions.

    Aggregates are supposed to be only those aggregates which refer to a
    post-aggregation function.
    """
    # If we have an aggregation function, then we consider the aggregate
    # already processed
    functions = []

    for aggregate in aggregates:
        # Ignore function if the backend already handles it
        try:
            factory = CALCULATED_AGGREGATIONS[aggregate.function]
        except KeyError:
            raise ArgumentError("Unknown post-calculation function '%s' for "
                                "aggregate '%s'" % (aggregate.function,
                                                    aggregate.name))

        if aggregate.measure:
            source = cube.measure_aggregate(aggregate.measure)
        else:
            raise InternalError("No measure specified for aggregate '%s' in "
                                "cube '%s'" % (aggregate.name, cube.name))

        func = factory(aggregate, source.ref, drilldown_levels, split)
        functions.append(func)

    return functions

def weighted_moving_average(values):
    n = len(values)
    denom = n * (n + 1) / 2
    total = 0.0
    idx = 1
    for val in values:
        total += float(idx) * float(val)
        idx += 1
    return round(total / denom, 4)


def simple_moving_average(values):
    # use all the values
    return round(compat.reduce(lambda i, c: float(c) + i, values, 0.0) / len(values), 2)

def simple_moving_sum(values):
    return compat.reduce(lambda i, c: i + c, values, 0)


def _variance(values):
    n, mean, std = len(values), 0, 0
    for a in values:
        mean = mean + a
    mean = mean / float(n)
    if n < 2:
        return mean, 0
    for a in values:
        std = std + (a - mean)**2
    return mean, (std / float(n-1))

def simple_relative_stdev(values):
    mean, var = _variance(values)
    return round(((sqrt(var)/mean) if mean > 0 else 0), 4)

def simple_variance(values):
    mean, var = _variance(values)
    return round(var, 2)

def simple_stdev(values):
    mean, var = _variance(values)
    return round(sqrt(var), 2)

def _window_function_factory(aggregate, source, drilldown_paths, split_cell, window_function, label):
    """Returns a moving average window function. `aggregate` is the target
    aggergate. `window_function` is concrete window function."""

    # If the level we're drilling to doesn't have aggregation_units configured,
    # we're not doing any calculations

    key_drilldown_paths = []
    window_size = None
    drilldown_paths = drilldown_paths or []

    if aggregate.window_size:
        window_size = aggregate.window_size
    else:
        # TODO: this is the old depreciated way, remove when not needed
        for path in drilldown_paths:
            relevant_level = path.levels[-1]
            these_num_units = None
            if relevant_level.info:
                these_num_units = relevant_level.info.get('aggregation_units', None)
            if these_num_units is None:
                key_drilldown_paths.append(path)
            else:
                window_size = these_num_units

    if window_size is None:
        window_size = 1

    elif not isinstance(window_size, int) or window_size < 1:
        raise ModelError("window size for aggregate '%s' sohuld be an integer "
                         "greater than or equeal 1" % aggregate.name)

    # Create a composite key for grouping:
    #   * split dimension, if used
    #   * key from drilldown path levels
    #
    # If no key_drilldown_paths, the key is always the empty tuple.

    window_key = []
    if split_cell:
        from .browser import SPLIT_DIMENSION_NAME
        window_key.append(SPLIT_DIMENSION_NAME)
    for dditem in key_drilldown_paths:
        window_key += [level.key.ref for level in dditem.levels]

    # TODO: this is temporary solution: for post-aggregate calculations we
    # consider the measure reference to be aggregated measure reference.
    # TODO: this does not work for implicit post-aggregate calculations

    function = WindowFunction(window_function, window_key,
                              target_attribute=aggregate.name,
                              source_attribute=source,
                              window_size=window_size,
                              label=label)
    return function

def get_key(record, composite_key):
    """Extracts a tuple of values from the `record` by `composite_key`"""
    return tuple(record.get(key) for key in composite_key)

class WindowFunction(object):
    def __init__(self, function, window_key, target_attribute,
                 source_attribute, window_size, label):
        """Creates a window function."""

        if not function:
            raise ArgumentError("No window function provided")
        if window_size < 1:
            raise ArgumentError("Window size should be >= 1")
        if not source_attribute:
            raise ArgumentError("Source attribute not specified")
        if not target_attribute:
            raise ArgumentError("Target attribute not specified")

        self.function = function
        self.window_key = tuple(window_key) if window_key else tuple()
        self.source_attribute = source_attribute
        self.target_attribute = target_attribute
        self.window_size = window_size
        self.window_values = {}
        self.label = label

    def __call__(self, record):
        """Collects the source value. If the window for the `window_key` is
        filled, then apply the window function and store the value in the
        `record` to key `target_attribute`."""

        key = get_key(record, self.window_key)

        # Get the window values by key. Create new if necessary.
        try:
            values = self.window_values[key]
        except KeyError:
            values = deque()
            self.window_values[key] = values

        value = record.get(self.source_attribute)

        # TODO: What about those window functions that would want to have empty
        # values?
        if value is not None:
            values.append(value)

        # Keep the window within the window size:
        while len(values) > self.window_size:
            values.popleft()

        # Compute, if we have the values
        if len(values) > 0:
            record[self.target_attribute] = self.function(values)



# TODO: make CALCULATED_AGGREGATIONS a namespace (see extensions.py)
CALCULATED_AGGREGATIONS = {
    "wma": partial(_window_function_factory,
                   window_function=weighted_moving_average,
                   label='Weighted Moving Avg. of {measure}'),
    "sma": partial(_window_function_factory,
                   window_function=simple_moving_average,
                   label='Simple Moving Avg. of {measure}'),
    "sms": partial(_window_function_factory,
                   window_function=simple_moving_sum,
                   label='Simple Moving Sum of {measure}'),
    "smstd": partial(_window_function_factory,
                     window_function=simple_stdev,
                     label='Moving Std. Deviation of {measure}'),
    "smrsd": partial(_window_function_factory,
                     window_function=simple_relative_stdev,
                     label='Moving Relative St. Dev. of {measure}'),
    "smvar": partial(_window_function_factory,
                     window_function=simple_variance,
                     label='Moving Variance of {measure}')
}

def available_calculators():
    """Returns a list of available calculators."""
    return CALCULATED_AGGREGATIONS.keys()

def aggregate_calculator_labels():
    return dict([(k, v.keywords['label']) for k, v in CALCULATED_AGGREGATIONS.items()])
