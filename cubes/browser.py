# -*- coding: utf-8 -*-

from __future__ import absolute_import

from collections import namedtuple

from .statutils import calculators_for_aggregates, available_calculators
from .calendar import CalendarMemberConverter
from .logging import get_logger
from .common import IgnoringDictionary
from .errors import ArgumentError, NoSuchAttributeError, HierarchyError
from .cells import Cell, PointCut, RangeCut, SetCut, cuts_from_string
from .model import string_to_dimension_level

from . import compat


__all__ = [
    "AggregationBrowser",
    "AggregationResult",
    "CalculatedResultIterator",
    "Facts",

    "Drilldown",
    "DrilldownItem",
    "levels_from_drilldown",

    "TableRow",
    "SPLIT_DIMENSION_NAME",
]

SPLIT_DIMENSION_NAME = '__within_split__'
NULL_PATH_VALUE = '__null__'


class AggregationBrowser(object):
    """Class for browsing data cube aggregations

    :Attributes:
      * `cube` - cube for browsing

    """

    __extension_type__ = "browser"
    __extension_suffix__ = "Browser"

    builtin_functions = []

    def __init__(self, cube, store=None, locale=None, **options):
        """Creates and initializes the aggregation browser. Subclasses should
        override this method. """
        super(AggregationBrowser, self).__init__()

        if not cube:
            raise ArgumentError("No cube given for aggregation browser")

        self.cube = cube
        self.store = store
        self.calendar = None

    def features(self):
        """Returns a dictionary of available features for the browsed cube.
        Default implementation returns an empty dictionary.

        Standard keys that might be present:

        * `actions` – list of actions that can be done with the cube, such as
          ``facts``, ``aggregate``, ``members``, ...
        * `post_processed_aggregates` – list of aggregates that are computed
          after the result is fetched from the source (not natively).

        Subclasses are advised to override this method.
        """
        return {}

    def aggregate(self, cell=None, aggregates=None, drilldown=None, split=None,
                  order=None, page=None, page_size=None, **options):

        """Return aggregate of a cell.

        Arguments:

        * `cell` – cell to aggregate. Can be either a :class:`cubes.Cell`
          object or a string with same syntax as for the Slicer :doc:`server
          <server>`
        * `aggregates` - list of aggregate measures. By default all
          cube's aggregates are included in the result.
        * `drilldown` - dimensions and levels through which to drill-down
        * `split` – cell for alternate 'split' dimension. Same type of
          argument as `cell`.
        * `order` – attribute order specification (see below)
        * `page` – page index when requesting paginated results
        * `page_size` – number of result items per page

        Drill down can be specified in two ways: as a list of dimensions or as
        a dictionary. If it is specified as list of dimensions, then cell is
        going to be drilled down on the next level of specified dimension. Say
        you have a cell for year 2010 and you want to drill down by months,
        then you specify ``drilldown = ["date"]``.

        If `drilldown` is a dictionary, then key is dimension or dimension
        name and value is last level to be drilled-down by. If the cell is at
        `year` level and drill down is: ``{ "date": "day" }`` then both
        `month` and `day` levels are added.

        If there are no more levels to be drilled down, an exception is
        raised. Say your model has three levels of the `date` dimension:
        `year`, `month`, `day` and you try to drill down by `date` at the next
        level then ``ValueError`` will be raised.

        Retruns a :class:`AggregationResult` object.

        If `split` is specified, then virtual dimension named
        `__within_split__` will be created and will contain `true` value if
        the cell is within the split cell and `false` if the cell is outside
        of the split.

        Note: subclasses should implement `provide_aggregate()` method.
        """

        if "measures" in options:
            raise ArgumentError("measures in aggregate are depreciated")

        aggregates = self.prepare_aggregates(aggregates)
        order = self.prepare_order(order, is_aggregate=True)

        converters = {
            "time": CalendarMemberConverter(self.calendar)
        }

        if cell is None:
            cell = Cell(self.cube)
        elif isinstance(cell, compat.string_type):
            cuts = cuts_from_string(self.cube, cell,
                                    role_member_converters=converters)
            cell = Cell(self.cube, cuts)

        if isinstance(split, compat.string_type):
            cuts = cuts_from_string(self.cube, split,
                                    role_member_converters=converters)
            split = Cell(self.cube, cuts)

        drilldon = Drilldown(drilldown, cell)

        result = self.provide_aggregate(cell,
                                        aggregates=aggregates,
                                        drilldown=drilldon,
                                        split=split,
                                        order=order,
                                        page=page,
                                        page_size=page_size,
                                        **options)

        #
        # Find post-aggregation calculations and decorate the result
        #
        calculated_aggs = [agg for agg in aggregates
                           if agg.function and \
                                not self.is_builtin_function(agg.function)]

        result.calculators = calculators_for_aggregates(self.cube,
                                                        calculated_aggs,
                                                        drilldown,
                                                        split)

        # Do calculated measures on summary if no drilldown or split
        if result.summary:
            for calc in result.calculators:
                calc(result.summary)

        return result

    def provide_aggregate(self, cell=None, measures=None, aggregates=None,
                          drilldown=None, split=None, order=None, page=None,
                          page_size=None, **options):
        """Method to be implemented by subclasses. The arguments are prepared
        by the superclass. Arguments:

        * `cell` – cell to be drilled down. Guaranteed to be a `Cell` object
          even for an empty cell
        * `aggregates` – list of aggregates to aggregate. Contains list of cube
          aggregate attribute objects.
        * `drilldown` – `Drilldown` instance
        * `split` – `Cell` instance
        * `order` – list of tuples: (`attribute`, `order`)

        """
        raise NotImplementedError("{} does not provide aggregate functionality." \
                                  .format(str(type(self))))

    def prepare_aggregates(self, aggregates=None, measures=None):
        """Prepares the aggregate list for aggregatios. `aggregates` might be a
        list of aggregate names or `MeasureAggregate` objects.

        Aggregates that are used in post-aggregation calculations are included
        in the result. This method is using `is_builtin_function()` to check
        whether the aggregate is native to the backend or not.

        If `measures` are specified, then aggregates that refer tho the
        measures in the list are returned.

        If no aggregates are specified then all cube's aggregates are returned.

        .. note::

            Either specify `aggregates` or `measures`, not both.
        """

        # Coalesce measures - make sure that they are Attribute objects, not
        # strings. Strings are converted to corresponding Cube measure
        # attributes
        # TODO: perhaps we might merge (without duplicates)

        if aggregates and measures:
            raise ArgumentError("Only aggregates or measures can be "
                                "specified, not both")
        if aggregates:
            try:
                aggregates = self.cube.get_aggregates(aggregates)
            except KeyError as e:
                raise NoSuchAttributeError("No measure aggregate '%s' in cube '%s'"
                                           % (str(e), str(self.cube)))
        elif measures:
            aggregates = []
            for measure in measures:
                aggregates += self.cube.aggregates_for_measure(measure)

        # If no aggregate is specified, then all are used
        aggregates = aggregates or self.cube.aggregates

        seen = set(a.name for a in aggregates)
        dependencies = []

        # Resolve aggregate dependencies for non-builtin functions:
        for agg in aggregates:
            if agg.measure and \
                    not self.is_builtin_function(agg.function) \
                    and agg.measure not in seen:
                seen.add(agg.measure)

                try:
                    aggregate = self.cube.aggregate(agg.measure)
                except NoSuchAttributeError as e:
                    raise NoSuchAttributeError("Cube '%s' has no measure aggregate "
                                            "'%s' for '%s'" % (self.cube.name,
                                                               agg.measure,
                                                               agg.name))
                dependencies.append(aggregate)

        aggregates += dependencies
        return aggregates

    def prepare_order(self, order, is_aggregate=False):
        """Prepares an order list. Returns list of tuples (`attribute`,
        `order_direction`). `attribute` is cube's attribute object."""

        order = order or []
        new_order = []

        for item in order:
            if isinstance(item, compat.string_type):
                name = item
                direction = None
            else:
                name, direction = item[0:2]

            attribute = None
            if is_aggregate:
                function = None
                try:
                    attribute = self.cube.aggregate(name)
                    function = attribute.function
                except NoSuchAttributeError:
                    attribute = self.cube.attribute(name)

                if function and not self.is_builtin_function(function):
                    # TODO: Temporary solution: get the original measure instead

                    try:
                        name = str(attribute.measure)
                        measure = self.cube.aggregate(name)
                    except NoSuchAttributeError:
                        measure = self.cube.measure(name)

                    attribute = measure
            else:
                attribute = self.cube.attribute(name)

            if attribute:
                new_order.append((attribute, direction))

        return new_order

    def assert_low_cardinality(self, cell, drilldown):
        """Raises `ArgumentError` when there is drilldown through high
        cardinality dimension or level and there is no condition in the cell
        for the level."""

        hc_levels = drilldown.high_cardinality_levels(cell)
        if hc_levels:
            names = [str(level) for level in hc_levels]
            names = ", ".join(names)
            raise ArgumentError("Can not drilldown on high-cardinality "
                                "levels (%s) without including both page_size "
                                "and page arguments, or else a point/set cut on the level"
                                % names)


    def is_builtin_function(self, function_name):
        """Returns `True` if function `function_name` is bult-in. Returns
        `False` if the browser can not compute the function and
        post-aggregation calculation should be used.

        Default implementation returns `True` for all unctions except those in
        :func:`available_calculators`. Subclasses are reommended to override
        this method if they have their own built-in version of the aggregate
        functions."""

        return function_name in available_calculators()

    def facts(self, cell=None, fields=None, **options):
        """Return an iterable object with of all facts within cell.
        `fields` is list of fields to be considered in the output.

        Subclasses overriding this method sould return a :class:`Facts` object
        and set it's `attributes` to the list of selected attributes."""
        raise NotImplementedError("{} does not provide facts functionality." \
                                  .format(str(type(self))))

    def fact(self, key):
        """Returns a single fact from cube specified by fact key `key`"""
        raise NotImplementedError("{} does not provide fact functionality." \
                                  .format(str(type(self))))

    def members(self, cell, dimension, depth=None, level=None, hierarchy=None,
                attributes=None, page=None, page_size=None, order=None,
                **options):
        """Return members of `dimension` with level depth `depth`. If `depth`
        is ``None``, all levels are returned. If no `hierarchy` is specified,
        then default dimension hierarchy is used.
        """
        order = self.prepare_order(order, is_aggregate=False)

        if cell is None:
            cell = Cell(self.cube)

        dimension = self.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)

        if depth is not None and level:
            raise ArgumentError("Both depth and level used, provide only one.")

        if not depth and not level:
            levels = hierarchy.levels
        elif depth == 0:
            raise ArgumentError("Depth for dimension members should not be 0")
        elif depth:
            levels = hierarchy.levels_for_depth(depth)
        else:
            index = hierarchy.level_index(level)
            levels = hierarchy.levels_for_depth(index+1)

        result = self.provide_members(cell,
                                      dimension=dimension,
                                      hierarchy=hierarchy,
                                      levels=levels,
                                      attributes=attributes,
                                      order=order,
                                      page=page,
                                      page_size=page_size,
                                      **options)
        return result

    def provide_members(self, *args, **kwargs):
        raise NotImplementedError("{} does not provide members functionality." \
                                  .format(str(type(self))))

    def test(self, **options):
        """Tests whether the cube can be used. Refer to the backend's
        documentation for more information about what is being tested."""
        raise NotImplementedError("{} does not provide test functionality." \
                                  .format(str(type(self))))

    def report(self, cell, queries):
        """Bundle multiple requests from `queries` into a single one.

        Keys of `queries` are custom names of queries which caller can later
        use to retrieve respective query result. Values are dictionaries
        specifying arguments of the particular query. Each query should
        contain at least one required value ``query`` which contains name of
        the query function: ``aggregate``, ``facts``, ``fact``, ``values`` and
        cell ``cell`` (for cell details). Rest of values are function
        specific, please refer to the respective function documentation for
        more information.

        Example::

            queries = {
                "product_summary" = { "query": "aggregate",
                                      "drilldown": "product" }
                "year_list" = { "query": "values",
                                "dimension": "date",
                                "depth": 1 }
            }

        Result is a dictionary where keys wil lbe the query names specified in
        report specification and values will be result values from each query
        call.::

            result = browser.report(cell, queries)
            product_summary = result["product_summary"]
            year_list = result["year_list"]

        This method provides convenient way to perform multiple common queries
        at once, for example you might want to have always on a page: total
        transaction count, total transaction amount, drill-down by year and
        drill-down by transaction type.

        Raises `cubes.ArgumentError` when there are no queries specified
        or if a query is of unknown type.

        .. `formatters` is a dictionary where keys are formatter names
        .. (arbitrary) and values are formatter instances.

        *Roll-up*

        Report queries might contain ``rollup`` specification which will
        result in "rolling-up" one or more dimensions to desired level. This
        functionality is provided for cases when you would like to report at
        higher level of aggregation than the cell you provided is in. It works
        in similar way as drill down in :meth:`AggregationBrowser.aggregate`
        but in the opposite direction (it is like ``cd ..`` in a UNIX shell).

        Example: You are reporting for year 2010, but you want to have a bar
        chart with all years. You specify rollup::

            ...
            "rollup": "date",
            ...

        Roll-up can be:

            * a string - single dimension to be rolled up one level
            * an array - list of dimension names to be rolled-up one level
            * a dictionary where keys are dimension names and values are
              levels to be rolled up-to

        *Future*

        In the future there might be optimisations added to this method,
        therefore it will become faster than subsequent separate requests.
        Also when used with Slicer OLAP service server number of HTTP call
        overhead is reduced.
        """

        # TODO: add this: cell_details=True, cell_details_key="_details"
        #
        # If `cell_details` is ``True`` then a key with name specified in
        # `cell_details_key` is added with cell details (see
        # `AggregationBrowser.cell_details() for more information). Default key
        # name is ``_cell``.

        report_result = {}

        for result_name, query in queries.items():
            query_type = query.get("query")
            if not query_type:
                raise ArgumentError("No report query for '%s'" % result_name)

            # FIXME: add: cell = query.get("cell")

            args = dict(query)
            del args["query"]

            # Note: we do not just convert name into function from symbol for possible future
            # more fine-tuning of queries as strings

            # Handle rollup
            rollup = query.get("rollup")
            if rollup:
                query_cell = cell.rollup(rollup)
            else:
                query_cell = cell

            if query_type == "aggregate":
                result = self.aggregate(query_cell, **args)

            elif query_type == "facts":
                result = self.facts(query_cell, **args)

            elif query_type == "fact":
                # Be more tolerant: by default we want "key", but "id" might be common
                key = args.get("key")
                if not key:
                    key = args.get("id")
                result = self.fact(key)

            elif query_type in ("values", "members"):
                # TODO: `values` are deprecated
                result = self.members(query_cell, **args)

            elif query_type == "details":
                # FIXME: depreciate this raw form
                result = self.cell_details(query_cell, **args)

            elif query_type == "cell":
                details = self.cell_details(query_cell, **args)
                cell_dict = query_cell.to_dict()

                for cut, detail in zip(cell_dict["cuts"], details):
                    cut["details"] = detail

                result = cell_dict
            else:
                raise ArgumentError("Unknown report query '%s' for '%s'" %
                                    (query_type, result_name))

            report_result[result_name] = result

        return report_result

    def cell_details(self, cell=None, dimension=None):
        """Returns details for the `cell`. Returned object is a list with one
        element for each cell cut. If `dimension` is specified, then details
        only for cuts that use the dimension are returned.

        Default implemenatation calls `AggregationBrowser.cut_details()` for
        each cut. Backends might customize this method to make it more
        efficient.

        .. warning:

            Return value of this method is not yet decided. Might be changed
            so that each element is a dictionary derived from cut (see
            `Cut.to_dict()` method of all Cut subclasses) and the details will
            be under the ``details`` key. Will depend on usability of current
            one.
        """

        # TODO: how we can add the cell as well?
        if not cell:
            return []

        if dimension:
            cuts = [cut for cut in cell.cuts
                    if str(cut.dimension) == str(dimension)]
        else:
            cuts = cell.cuts

        details = [self.cut_details(cut) for cut in cuts]

        return details

    def cut_details(self, cut):
        """Gets details for a `cut` which should be a `Cut` instance.

        * `PointCut` - all attributes for each level in the path
        * `SetCut` - list of `PointCut` results, one per path in the set
        * `RangeCut` - `PointCut`-like results for lower range (from) and
          upper range (to)

        """

        dimension = self.cube.dimension(cut.dimension)

        if isinstance(cut, PointCut):
            details = self._path_details(dimension, cut.path, cut.hierarchy)

        elif isinstance(cut, SetCut):
            details = [self._path_details(dimension, path, cut.hierarchy) for path in cut.paths]

        elif isinstance(cut, RangeCut):
            details = {
                "from": self._path_details(dimension, cut.from_path,
                                           cut.hierarchy),
                "to": self._path_details(dimension, cut.to_path, cut.hierarchy)
            }

        else:
            raise Exception("Unknown cut type %s" % cut)

        return details

    def _path_details(self, dimension, path, hierarchy=None):
        """Returns a list of details for a path. Each element of the list
        corresponds to one level of the path and is represented by a
        dictionary. The keys are dimension level attributes. Returns ``None``
        when there is no such path for the dimension.

        Two redundant keys are added: ``_label`` and ``_key`` representing
        level key and level label (based on `Level.label_attribute_key`).

        .. note::

            The behaviour should be configurable: we either return all the
            keys or just a label and a key.
        """

        hierarchy = dimension.hierarchy(hierarchy)
        details = self.path_details(dimension, path, hierarchy)

        if not details:
            return None

        if dimension.is_flat and not dimension.has_details:
            name = dimension.all_attributes[0].name
            value = details.get(name)
            item = {name: value}
            item["_key"] = value
            item["_label"] = value
            result = [item]
        else:
            result = []
            for level in hierarchy.levels_for_path(path):
                item = {a.ref: details.get(a.ref) for a in
                        level.attributes}
                item["_key"] = details.get(level.key.ref)
                item["_label"] = details.get(level.label_attribute.ref)
                result.append(item)

        return result

    def path_details(self, dimension, path, hierarchy):
        """Returns empty path details. Default fall-back for backends that do
        not support the path details. The level key and label are the same
        derived from the key."""

        detail = {}
        for level, key in zip(hierarchy.levels, path):
            for attr in level.attributes:
                if attr == level.key or attr == level.label_attribute:
                    detail[attr.ref] = key
                else:
                    detail[attr.ref] = None

        return detail

class Facts(object):
    def __init__(self, facts, attributes):
        """A facts iterator object returned by the browser's `facts()`
        method."""

        self.facts = facts or []
        self.attributes = attributes

    def __iter__(self):
        return iter(self.facts)


TableRow = namedtuple("TableRow", ["key", "label", "path", "is_base", "record"])


class CalculatedResultIterator(object):
    """
    Iterator that decorates data items
    """
    def __init__(self, calculators, iterator):
        self.calculators = calculators
        self.iterator = iterator

    def __iter__(self):
        return self

    def __next__(self):
        # Apply calculators to the result record
        item = next(self.iterator)
        for calc in self.calculators:
            calc(item)
        return item

    next = __next__

class AggregationResult(object):
    """Result of aggregation or drill down.

    Attributes:

    * `cell` – cell that this result is aggregate of
    * `summary` - dictionary of summary row fields
    * `cells` - list of cells that were drilled-down
    * `total_cell_count` - number of total cells in drill-down (after limit,
      before pagination)
    * `aggregates` – aggregates that were selected in aggregation. List of
    `MeasureAggregate` objects.
    * `remainder` - summary of remaining cells (not yet implemented)
    * `levels` – aggregation levels for dimensions that were used to drill-
      down

    .. note::

        Implementors of aggregation browsers should populate `cell`,
        `measures` and `levels` from the aggregate query.

    """
    def __init__(self, cell=None, aggregates=None, drilldown=None,
                 has_split=False):
        """Create an aggergation result object. `cell` – a :class:`cubes.Cell`
        object used for this aggregation, `aggregates` – list of aggregate
        objects selected for this a aggregation, `drilldown` – a
        :class:`cubes.Drilldown` object representing list of dimensions and
        hierarchies the result is drilled-down by, `has_split` – flag whether
        the result has a split dimension."""

        super(AggregationResult, self).__init__()
        self.cell = cell

        # Note: aggregates HAS to be a list of Aggregate objects, not just
        # list of strings
        self.aggregates = aggregates

        self.drilldown = drilldown

        # TODO: Experimental, undocumented
        if drilldown:
            attrs = [attr.ref for attr in self.drilldown.all_attributes]
            self.attributes = attrs
        else:
            self.attributes = []

        self.has_split = has_split

        if drilldown:
            self.levels = drilldown.result_levels()
        else:
            self.levels = None

        self.summary = {}
        self._cells = []
        self.total_cell_count = None
        self.remainder = {}
        self.labels = []
        self.calculators = []

    @property
    def cells(self):
        return self._cells

    @cells.setter
    def cells(self, val):
        # decorate iterable with calcs if needed
        if self.calculators:
            val = CalculatedResultIterator(self.calculators, iter(val))
        self._cells = val

    def to_dict(self):
        """Return dictionary representation of the aggregation result. Can be
        used for JSON serialisation."""

        d = IgnoringDictionary()

        d["summary"] = self.summary
        d["remainder"] = self.remainder
        d["cells"] = self.cells
        d["total_cell_count"] = self.total_cell_count

        d["aggregates"] = [str(m) for m in self.aggregates]

        # We want to set None
        d.set("cell", [cut.to_dict() for cut in self.cell.cuts])

        d["levels"] = self.levels

        # TODO: New, undocumented for now
        d.set("attributes", self.attributes)
        d["has_split"] = self.has_split


        return d

    def has_dimension(self, dimension):
        """Returns `True` if the result was drilled down by `dimension` (at
        any level)"""

        if not self.levels:
            return False

        return str(dimension) in self.levels

    def table_rows(self, dimension, depth=None, hierarchy=None):
        """Returns iterator of drilled-down rows which yields a named tuple with
        named attributes: (key, label, path, record). `depth` is last level of
        interest. If not specified (set to ``None``) then deepest level for
        `dimension` is used.

        * `key`: value of key dimension attribute at level of interest
        * `label`: value of label dimension attribute at level of interest
        * `path`: full path for the drilled-down cell
        * `is_base`: ``True`` when dimension element is base (can not drill
          down more)
        * `record`: all drill-down attributes of the cell

        Example use::

            for row in result.table_rows(dimension):
                print "%s: %s" % (row.label, row.record["fact_count"])

        `dimension` has to be :class:`cubes.Dimension` object. Raises
        `TypeError` when cut for `dimension` is not `PointCut`.
        """

        cut = self.cell.point_cut_for_dimension(dimension)

        path = cut.path if cut else []

        # FIXME: use hierarchy from cut (when implemented)
        dimension = self.cell.cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)

        if self.levels:
            # Convert "levels" to a dictionary:
            # all_levels = dict((dim, levels) for dim, levels in self.levels)
            dim_levels = self.levels.get(str(dimension), [])
            is_base = len(dim_levels) >= len(hierarchy)
        else:
            is_base = len(hierarchy) == 1

        if depth:
            current_level = hierarchy[depth - 1]
        else:
            levels = hierarchy.levels_for_path(path, drilldown=True)
            current_level = levels[-1]

        level_key = current_level.key.ref
        level_label = current_level.label_attribute.ref

        for record in self.cells:
            drill_path = path[:] + [record[level_key]]

            row = TableRow(record[level_key],
                           record[level_label],
                           drill_path,
                           is_base,
                           record)
            yield row

    def __iter__(self):
        """Return cells as iterator"""
        return iter(self.cells)

    def cached(self):
        """Return shallow copy of the receiver with cached cells. If cells are
        an iterator, they are all fetched in a list.

        .. warning::

            This might be expensive for large results.
        """

        result = AggregationResult()
        result.cell = self.cell
        result.aggregates = self.aggregates
        result.levels = self.levels
        result.summary = self.summary
        result.total_cell_count = self.total_cell_count
        result.remainder = self.remainder

        # Cache cells from an iterator
        result.cells = list(self.cells)
        return result


class Drilldown(object):
    def __init__(self, drilldown=None, cell=None):
        """Creates a drilldown object for `drilldown` specifictation of `cell`.
        The drilldown object can be used by browsers for convenient access to
        various drilldown properties.

        Attributes:

        * `drilldown` – list of drilldown items (named tuples) with attributes:
           `dimension`, `hierarchy`, `levels` and `keys`
        * `dimensions` – list of dimensions used in this drilldown

        The `Drilldown` object can be accessed by item index ``drilldown[0]``
        or dimension name ``drilldown["date"]``. Iterating the object yields
        all drilldown items.
        """
        self.drilldown = levels_from_drilldown(cell, drilldown)
        self.dimensions = []
        self._contained_dimensions = set()

        for dd in self.drilldown:
            self.dimensions.append(dd.dimension)
            self._contained_dimensions.add(dd.dimension.name)

    def __str__(self):
        return ",".join(self.items_as_strings())

    def items_as_strings(self):
        """Returns drilldown items as strings: ``dimension@hierarchy:level``.
        If hierarchy is dimension's default hierarchy, then it is not included
        in the string: ``dimension:level``"""

        strings = []

        for item in self.drilldown:
            if item.hierarchy != item.dimension.hierarchy():
                hierstr = "@%s" % str(item.hierarchy)
            else:
                hierstr = ""

            ddstr = "%s%s:%s" % (item.dimension.name,
                                 hierstr,
                                 item.levels[-1].name)
            strings.append(ddstr)

        return strings

    def drilldown_for_dimension(self, dim):
        """Returns drilldown items for dimension `dim`."""
        items = []
        dimname = str(dim)
        for item in self.drilldown:
            if str(item.dimension) == dimname:
                items.append(item)

        return items

    def __getitem__(self, key):
        return self.drilldown[key]

    def deepest_levels(self):
        """Returns a list of tuples: (`dimension`, `hierarchy`, `level`) where
        `level` is the deepest level drilled down to.

        This method is currently used for preparing the periods-to-date
        conditions.

        See also: :meth:`cubes.Cell.deepest_levels`
        """

        levels = []

        for dditem in self.drilldown:
            item = (dditem.dimension, dditem.hierarchy, dditem.levels[-1])
            levels.append(item)

        return levels

    def high_cardinality_levels(self, cell):
        """Returns list of levels in the drilldown that are of high
        cardinality and there is no cut for that level in the `cell`."""

        for item in self.drilldown:
            dim, hier, _ = item[0:3]
            not_contained = []

            for level in item.levels:
                if (level.cardinality == "high" or dim.cardinality == "high") \
                        and not cell.contains_level(dim, level, hier):
                    not_contained.append(level)

            if not_contained:
                return not_contained

        return []

    def result_levels(self, include_split=False):
        """Returns a dictionary where keys are dimension names and values are
        list of level names for the drilldown. Use this method to populate the
        result levels attribute.

        If `include_split` is `True` then split dimension is included."""
        result = {}

        for item in self.drilldown:
            dim, hier, levels = item[0:3]

            if dim.hierarchy().name == hier.name:
                dim_key = dim.name
            else:
                dim_key = "%s@%s" % (dim.name, hier.name)

            result[dim_key] = [str(level) for level in levels]

        if include_split:
            result[SPLIT_DIMENSION_NAME] = [SPLIT_DIMENSION_NAME]

        return result

    @property
    def key_attributes(self):
        """Returns only key attributes of all levels in the drilldown. Order
        is by the drilldown item, then by the levels and finally by the
        attribute in the level.

        .. versionadded:: 1.1
        """
        attributes = []
        for item in self.drilldown:
            attributes += [level.key for level in item.levels]

        return attributes

    @property
    def all_attributes(self):
        """Returns attributes of all levels in the drilldown. Order is by the
        drilldown item, then by the levels and finally by the attribute in the
        level."""
        attributes = []
        for item in self.drilldown:
            for level in item.levels:
                attributes += level.attributes

        return attributes

    @property
    def natural_order(self):
        """Return a natural order for the drill-down. This order can be merged
        with user-specified order. Returns a list of tuples:
        (`attribute_name`, `order`)."""

        order = []

        for item in self.drilldown:
            for level in item.levels:
                lvl_attr = level.order_attribute or level.key
                lvl_order = level.order or 'asc'
                order.append((lvl_attr, lvl_order))

        return order

    def has_dimension(self, dim):
        return str(dim) in self._contained_dimensions

    def __len__(self):
        return len(self.drilldown)

    def __iter__(self):
        return self.drilldown.__iter__()

    def __nonzero__(self):
        return len(self.drilldown) > 0

DrilldownItem = namedtuple("DrilldownItem",
                           ["dimension", "hierarchy", "levels", "keys"])


# TODO: move this to Drilldown
def levels_from_drilldown(cell, drilldown):
    """Converts `drilldown` into a list of levels to be used to drill down.
    `drilldown` can be:

    * list of dimensions
    * list of dimension level specifier strings
    * (``dimension@hierarchy:level``) list of tuples in form (`dimension`,
      `hierarchy`, `levels`, `keys`).

    If `drilldown is a list of dimensions or if the level is not specified,
    then next level in the cell is considered. The implicit next level is
    determined from a `PointCut` for `dimension` in the `cell`.

    For other types of cuts, such as range or set, "next" level is the first
    level of hierarachy.

    Returns a list of drilldown items with attributes: `dimension`,
    `hierarchy` and `levels` where `levels` is a list of levels to be drilled
    down.
    """

    if not drilldown:
        return []

    result = []

    # If the drilldown is a list, convert it into a dictionary
    if isinstance(drilldown, dict):
        logger = get_logger()
        logger.warn("drilldown as dictionary is depreciated. Use a list of: "
                    "(dim, hierarchy, level) instead")
        drilldown = [(dim, None, level) for dim, level in drilldown.items()]

    for obj in drilldown:
        if isinstance(obj, compat.string_type):
            obj = string_to_dimension_level(obj)
        elif isinstance(obj, DrilldownItem):
            obj = (obj.dimension, obj.hierarchy, obj.levels[-1])
        elif len(obj) != 3:
            raise ArgumentError("Drilldown item should be either a string "
                                "or a tuple of three elements. Is: %s" %
                                (obj, ))

        dim, hier, level = obj
        dim = cell.cube.dimension(dim)

        hier = dim.hierarchy(hier)

        if level:
            index = hier.level_index(level)
            levels = hier[:index + 1]
        elif dim.is_flat:
            levels = hier[:]
        else:
            cut = cell.point_cut_for_dimension(dim)
            if cut:
                cut_hierarchy = dim.hierarchy(cut.hierarchy)
                depth = cut.level_depth()
                # inverted cut means not to auto-drill to the next level
                if cut.invert:
                    depth -= 1
                # a flat dimension means not to auto-drill to the next level
            else:
                cut_hierarchy = hier
                depth = 0

            if cut_hierarchy != hier:
                raise HierarchyError("Cut hierarchy %s for dimension %s is "
                                     "different than drilldown hierarchy %s. "
                                     "Can not determine implicit next level."
                                     % (hier, dim, cut_hierarchy))

            if depth >= len(hier):
                raise HierarchyError("Hierarchy %s in dimension %s has only "
                                     "%d levels, can not drill to %d" %
                                     (hier, dim, len(hier), depth + 1))

            levels = hier[:depth + 1]

        levels = tuple(levels)
        keys = [level.key.ref for level in levels]
        result.append(DrilldownItem(dim, hier, levels, keys))

    return result
