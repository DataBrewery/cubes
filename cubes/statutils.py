from collections import deque
from .model import Attribute
from .browser import SPLIT_DIMENSION_NAME
from .errors import *

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

    names = [a.name for a in aggregates]
    for aggregate in aggregates:
        # Ignore function if the backend already handles it
        if not aggregate.function or aggregate.function in backend_functions:
            continue

        try:
            factory = CALCULATED_AGGREGATIONS[aggregate.function]
        except KeyError:
            raise ArgumentError("Unknown post-calculation function '%s' for "
                                "aggregate '%s'" % (aggregate.function,
                                                    aggregate.name))

        if aggregate.measure not in names:
            raise ModelError("Unknown aggregate measure '%s'"
                             % str(aggregate.measure))

        func = factory(aggregate, drilldown_levels, split)
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
    return round(reduce(lambda i, c: float(c) + i, values, 0.0) / len(values), 2)


def weighted_moving_average_factory(aggregate, drilldown_paths, split_cell):
    return _moving_average_factory(aggregate, drilldown_paths, split_cell,
                                   weighted_moving_average)


def simple_moving_average_factory(aggregate, drilldown_paths, split_cell):
    return _moving_average_factory(aggregate, drilldown_paths, split_cell,
                                   simple_moving_average)


def _moving_average_factory(aggregate, drilldown_paths, split_cell, avg_func):
    """Returns a moving average window function. `aggregate` is the target
    aggergate. `avg_function` is concrete window function."""

    # If the level we're drilling to doesn't have aggregation_units configured,
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

    # Coalesce the units

    if num_units is None or not isinstance(num_units, int) or num_units < 1:
        num_units = 1

    # Create a composite key for grouping:
    #   * split dimension, if used
    #   * key from drilldown path levels
    #
    # If no key_drilldown_paths, the key is always the empty tuple.

    window_key = []
    if split_cell:
        window_key.append(SPLIT_DIMENSION_NAME)
    for dditem in key_drilldown_paths:
        window_key += [level.key.ref() for level in dditem.levels]

    # TODO: this is temporary solution: for post-aggregate calculations we
    # consider the measure reference to be aggregated measure reference.
    # TODO: this does not work for implicit post-aggregate calculations

    source = aggregate.measure
    function = WindowFunction(avg_func, window_key,
                              target_attribute=aggregate.name,
                              source_attribute=source,
                              window_size=num_units)
    return function

def get_key(record, composite_key):
    """Extracts a tuple of values from the `record` by `composite_key`"""
    return tuple(record.get(key) for key in composite_key)

class WindowFunction(object):
    def __init__(self, function, window_key, target_attribute,
                 source_attribute, window_size):
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
    "sma": simple_moving_average_factory,
    "wma": weighted_moving_average_factory
}

