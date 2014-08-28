# -*- coding: utf-8 -*-

from __future__ import absolute_import

import copy
import re
from collections import namedtuple

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from .errors import *
from .model import Dimension, Cube
from .common import IgnoringDictionary
from .logging import get_logger
from .extensions import Extensible
from .calendar import CalendarMemberConverter
from . import compat


__all__ = [
    "AggregationBrowser",
    "AggregationResult",
    "CalculatedResultIterator",
    "Facts",

    "Cell",
    "Cut",
    "PointCut",
    "RangeCut",
    "SetCut",

    "cuts_from_string",
    "string_from_cuts",
    "string_from_path",
    "string_from_hierarchy",
    "string_to_drilldown",
    "path_from_string",
    "cut_from_string",
    "cut_from_dict",

    "Drilldown",
    "DrilldownItem",
    "levels_from_drilldown",

    "TableRow",
    "CrossTable",
    "cross_table",
    "SPLIT_DIMENSION_NAME",
]

SPLIT_DIMENSION_NAME = '__within_split__'
NULL_PATH_VALUE = '__null__'


class AggregationBrowser(Extensible):
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
        raise NotImplementedError

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
                    not self.is_builtin_function(agg.function, agg) \
                    and agg.measure not in seen:
                seen.add(agg.measure)

                try:
                    aggregate = self.cube.measure_aggregate(agg.measure)
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
                    attribute = self.cube.measure_aggregate(name)
                    function = attribute.function
                except NoSuchAttributeError:
                    attribute = self.cube.attribute(name)

                if function and not self.is_builtin_function(function,
                                                             attribute):
                    # TODO: Temporary solution: get the original measure instead

                    try:
                        name = str(attribute.measure)
                        measure = self.cube.measure_aggregate(name)
                    except NoSuchAttributeError:
                        measure = self.cube.measure(name)

                    self.logger.warn("ordering of post-processed aggregate"
                                     " %s will be based on measure %s"
                                     % (attribute.name, measure.name))
                    attribute = measure
            else:
                attribute = self.cube.attribute(name)

            if attribute:
                new_order.append( (attribute, direction) )

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


    def is_builtin_function(self, function_name, aggregate):
        """Returns `True` if function `function_name` for `aggregate` is
        bult-in. Returns `False` if the browser can not compute the function
        and post-aggregation calculation should be used.

        Subclasses should override this method."""
        raise NotImplementedError

    def facts(self, cell=None, fields=None, **options):
        """Return an iterable object with of all facts within cell.
        `fields` is list of fields to be considered in the output.

        Subclasses overriding this method sould return a :class:`Facts` object
        and set it's `attributes` to the list of selected attributes."""

        raise NotImplementedError

    def fact(self, key):
        """Returns a single fact from cube specified by fact key `key`"""
        raise NotImplementedError

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

    def values(self, *args, **kwargs):
        # TODO: depreciated
        self.logger.warn("values() is depreciated, use members()")
        return self.members(*args, **kwargs)

    def test(self, **options):
        """Tests whether the cube can be used. Refer to the backend's
        documentation for more information about what is being tested."""
        raise NotImplementedError

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

            elif query_type == "values":
                result = self.values(query_cell, **args)

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

        if (dimension.is_flat and not dimension.has_details):
            name = dimension.all_attributes[0].name
            value = details.get(name)
            item = {name: value}
            item["_key"] = value
            item["_label"] = value
            result = [item]
        else:
            result = []
            for level in hierarchy.levels_for_path(path):
                item = {a.ref(): details.get(a.ref()) for a in
                        level.attributes}
                item["_key"] = details.get(level.key.ref())
                item["_label"] = details.get(level.label_attribute.ref())
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
                    detail[attr.ref()] = key
                else:
                    detail[attr.ref()] = None

        return detail

class Facts(object):
    def __init__(self, facts, attributes):
        """A facts iterator object returned by the browser's `facts()`
        method."""

        self.facts = facts or []
        self.attributes = attributes

    def __iter__(self):
        return iter(self.facts)


class Cell(object):
    """Part of a cube determined by slicing dimensions. Immutable object."""
    def __init__(self, cube=None, cuts=None):
        if not isinstance(cube, Cube):
            raise ArgumentError("Cell cube should be sublcass of Cube, "
                                "provided: %s" % type(cube).__name__)
        self.cube = cube
        self.cuts = cuts if cuts is not None else []

    def __and__(self, other):
        """Returns a new cell that is a conjunction of the two provided
        cells. The cube has to match."""
        if self.cube != other.cube:
            raise ArgumentError("Can not combine two cells from different "
                                "cubes '%s' and '%s'."
                                % (self.name, other.name))
        cuts = self.cuts + other.cuts
        return Cell(self.cube, cuts=cuts)

    def to_dict(self):
        """Returns a dictionary representation of the cell"""
        result = {
            "cube": str(self.cube.name),
            "cuts": [cut.to_dict() for cut in self.cuts]
        }

        return result

    def slice(self, cut):
        """Returns new cell by slicing receiving cell with `cut`. Cut with
        same dimension as `cut` will be replaced, if there is no cut with the
        same dimension, then the `cut` will be appended.
        """

        # Fix for wrong early design decision:
        if isinstance(cut, Dimension) or isinstance(cut, compat.string_type):
            raise CubesError("slice() should now be called with a cut (since v0.9.2). To get "
                             "original behaviour of one-dimension point cut, "
                             "use cell.slice(PointCut(dim,path))")

        cuts = self.cuts[:]
        index = self._find_dimension_cut(cut.dimension)
        if index is not None:
            cuts[index] = cut
        else:
            cuts.append(cut)

        return Cell(cube=self.cube, cuts=cuts)

    def _find_dimension_cut(self, dimension):
        """Returns index of first occurence of cut for `dimension`. Returns
        ``None`` if no cut with `dimension` is found."""
        names = [str(cut.dimension) for cut in self.cuts]

        try:
            index = names.index(str(dimension))
            return index
        except ValueError:
            return None

    def point_slice(self, dimension, path):
        """
        Create another cell by slicing receiving cell through `dimension`
        at `path`. Receiving object is not modified. If cut with dimension
        exists it is replaced with new one. If path is empty list or is none,
        then cut for given dimension is removed.

        Example::

            full_cube = Cell(cube)
            contracts_2010 = full_cube.point_slice("date", [2010])

        Returns: new derived cell object.

        .. warning::

            Depreiated. Use :meth:`cell.slice` instead with argument
            `PointCut(dimension, path)`

        """

        dimension = self.cube.dimension(dimension)
        cuts = self.dimension_cuts(dimension, exclude=True)
        if path:
            cut = PointCut(dimension, path)
            cuts.append(cut)
        return Cell(cube=self.cube, cuts=cuts)

    def drilldown(self, dimension, value, hierarchy=None):
        """Create another cell by drilling down `dimension` next level on
        current level's key `value`.

        Example::

            cell = cubes.Cell(cube)
            cell = cell.drilldown("date", 2010)
            cell = cell.drilldown("date", 1)

        is equivalent to:

            cut = cubes.PointCut("date", [2010, 1])
            cell = cubes.Cell(cube, [cut])

        Reverse operation is ``cubes.rollup("date")``

        Works only if the cut for dimension is `PointCut`. Otherwise the
        behaviour is undefined.

        If `hierarchy` is not specified (by default) then default dimension
        hierarchy is used.

        Returns new derived cell object.
        """
        dimension = self.cube.dimension(dimension)
        dim_cut = self.cut_for_dimension(dimension)

        old_path = dim_cut.path if dim_cut else []
        new_cut = PointCut(dimension, old_path + [value], hierarchy=hierarchy)

        cuts = [cut for cut in self.cuts if cut is not dim_cut]
        cuts.append(new_cut)

        return Cell(cube=self.cube, cuts=cuts)

    def multi_slice(self, cuts):
        """Create another cell by slicing through multiple slices. `cuts` is a
        list of `Cut` object instances. See also :meth:`Cell.slice`."""

        if isinstance(cuts, dict):
            raise CubesError("dict type is not supported any more, use list of Cut instances")

        cell = self
        for cut in cuts:
            cell = cell.slice(cut)

        return cell

    def cut_for_dimension(self, dimension):
        """Return first found cut for given `dimension`"""
        dimension = self.cube.dimension(dimension)

        cut_dimension = None
        for cut in self.cuts:
            cut_dimension = self.cube.dimension(cut.dimension)

            if cut_dimension == dimension:
                return cut

        return None

    def point_cut_for_dimension(self, dimension):
        """Return first point cut for given `dimension`"""

        dimension = self.cube.dimension(dimension)

        cutdim = None
        for cut in self.cuts:
            cutdim = self.cube.dimension(cut.dimension)
            if isinstance(cut, PointCut) and cutdim == dimension:
                return cut

        return None

    def rollup_dim(self, dimension, level=None, hierarchy=None):
        """Rolls-up cell - goes one or more levels up through dimension
        hierarchy. If there is no level to go up (we are at the top level),
        then the cut is removed.

        If no `hierarchy` is specified, then the default dimension's hierarchy
        is used.

        Returns new cell object.
        """

        # FIXME: make this the default roll-up
        # Reason:
        #     * simpler to use
        #     * can be used more nicely in Jinja templates

        dimension = self.cube.dimension(dimension)
        dim_cut = self.point_cut_for_dimension(dimension)

        if not dim_cut:
            return copy.copy(self)
            # raise ValueError("No cut to roll-up for dimension '%s'" % dimension.name)

        cuts = [cut for cut in self.cuts if cut is not dim_cut]

        hier = dimension.hierarchy(hierarchy)
        rollup_path = hier.rollup(dim_cut.path, level)

        # If the rollup path is empty, we are at the top level therefore we
        # are removing the cut for the dimension.

        if rollup_path:
            new_cut = PointCut(dimension, rollup_path, hierarchy=hierarchy)
            cuts.append(new_cut)

        return Cell(cube=self.cube, cuts=cuts)

    def rollup(self, rollup):
        """Rolls-up cell - goes one or more levels up through dimension
        hierarchy. It works in similar way as drill down in
        :meth:`AggregationBrowser.aggregate` but in the opposite direction (it
        is like ``cd ..`` in a UNIX shell).

        Roll-up can be:

            * a string - single dimension to be rolled up one level
            * an array - list of dimension names to be rolled-up one level
            * a dictionary where keys are dimension names and values are
              levels to be rolled up-to

        .. note::

                Only default hierarchy is currently supported.
        """

        # FIXME: rename this to something like really_complex_rollup :-)
        # Reason:
        #     * see reasons above for rollup_dim()
        #     * used only by Slicer server

        cuts = OrderedDict()
        for cut in self.cuts:
            dim = self.cube.dimension(cut.dimension)
            cuts[dim.name] = cut

        new_cuts = []

        # If it is a string, handle it as list of single string
        if isinstance(rollup, compat.string_type):
            rollup = [rollup]

        if type(rollup) == list or type(rollup) == tuple:
            for dim_name in rollup:
                cut = cuts.get(dim_name)
                if cut is None:
                    continue
                #     raise ValueError("No cut to roll-up for dimension '%s'" % dim_name)
                if type(cut) != PointCut:
                    raise NotImplementedError("Only PointCuts are currently supported for "
                                              "roll-up (rollup dimension: %s)" % dim_name)

                dim = self.cube.dimension(cut.dimension)
                hier = dim.default_hierarchy

                rollup_path = hier.rollup(cut.path)

                cut = PointCut(cut.dimension, rollup_path)
                new_cuts.append(cut)

        elif isinstance(self.drilldown, dict):
            for (dim_name, level_name) in rollup.items():
                cut = cuts[dim_name]
                if not cut:
                    raise ArgumentError("No cut to roll-up for dimension '%s'" % dim_name)
                if type(cut) != PointCut:
                    raise NotImplementedError("Only PointCuts are currently supported for "
                                              "roll-up (rollup dimension: %s)" % dim_name)

                dim = selfcube.dimension(cut.dimension)
                hier = dim.default_hierarchy

                rollup_path = hier.rollup(cut.path, level_name)

                cut = PointCut(cut.dimension, rollup_path)
                new_cuts.append(cut)
        else:
            raise ArgumentError("Rollup is of unknown type: %s" % self.drilldown.__class__)

        cell = Cell(cube=self.cube, cuts=new_cuts)
        return cell

    def level_depths(self):
        """Returns a dictionary of dimension names as keys and level depths
        (index of deepest level)."""

        levels = {}

        for cut in self.cuts:
            level = cut.level_depth()
            dim = self.cube.dimension(cut.dimension)
            dim_name = str(dim)

            levels[dim_name] = max(level, levels.get(dim_name))

        return levels

    def deepest_levels(self, include_empty=False):
        """Returns a list of tuples: (`dimension`, `hierarchy`, `level`) where
        `level` is the deepest level specified in the respective cut. If no
        level is specified (empty path) and `include_empty` is `True`, then the
        level will be `None`. If `include_empty` is `True` then empty levels
        are not included in the result.

        This method is currently used for preparing the periods-to-date
        conditions.

        See also: :meth:`cubes.Drilldown.deepest_levels`
        """

        levels = []

        for cut in self.cuts:
            depth = cut.level_depth()
            dim = self.cube.dimension(cut.dimension)
            hier = dim.hierarchy(cut.hierarchy)
            if depth:
                item = (dim, hier, hier[depth-1])
            elif include_empty:
                item = (dim, hier, None)
            levels.append(item)

        return levels

    def is_base(self, dimension, hierarchy=None):
        """Returns ``True`` when cell is base cell for `dimension`. Cell
        is base if there is a point cut with path referring to the
        most detailed level of the dimension `hierarchy`."""

        hierarchy = dimension.hierarchy(hierarchy)
        cut = self.point_cut_for_dimension(dimension)
        if cut:
            return cut.level_depth() >= len(hierarchy)
        else:
            return False

    def contains_level(self, dim, level, hierarchy=None):
        """Returns `True` if one of the cuts contains `level` of dimension
        `dim`. If `hierarchy` is not specified, then dimension's default
        hierarchy is used."""

        dim = self.cube.dimension(dim)
        hierarchy = dim.hierarchy(hierarchy)

        for cut in self.dimension_cuts(dim):
            if str(cut.hierarchy) != str(hierarchy):
                continue
            if isinstance(cut, PointCut):
                if level in hierarchy.levels_for_path(cut.path):
                    return True
            if isinstance(cut, SetCut):
                for path in cut.paths:
                    if level in hierarchy.levels_for_path(path):
                        return True
        return False

    def dimension_cuts(self, dimension, exclude=False):
        """Returns cuts for `dimension`. If `exclude` is `True` then the
        effect is reversed: return all cuts except those with `dimension`."""
        dimension = self.cube.dimension(dimension)
        cuts = []
        for cut in self.cuts:
            cut_dimension = self.cube.dimension(cut.dimension)
            if (exclude and cut_dimension != dimension) \
                    or (not exclude and cut_dimension == dimension):
                cuts.append(cut)
        return cuts

    def public_cell(self):
        """Returns a cell that contains only non-hidden cuts. Hidden cuts are
        mostly generated cuts by a backend or an extension. Public cell is a
        cell to be presented to the front-end."""

        cuts = [cut for cut in self.cuts if not cut.hidden]

        return Cell(self.cube, cuts)

    def __eq__(self, other):
        """cells are considered equal if:
            * they refer to the same cube
            * they have same set of cuts (regardless of their order)
        """

        if self.cube != other.cube:
            return False
        elif len(self.cuts) != len(other.cuts):
            return False

        for cut in self.cuts:
            if cut not in other.cuts:
                return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_str(self):
        """Return string representation of the cell by using standard
        cuts-to-string conversion."""
        return string_from_cuts(self.cuts)

    def __str__(self):
        """Return string representation of the cell by using standard
        cuts-to-string conversion."""
        return string_from_cuts(self.cuts)

    def __repr__(self):
        return 'Cell(%s: %s)' % (str(self.cube), self.to_str() or 'All')

    def __nonzero__(self):
        """Returns `True` if the cell contains cuts."""
        return bool(self.cuts)

CUT_STRING_SEPARATOR_CHAR = "|"
DIMENSION_STRING_SEPARATOR_CHAR = ":"
PATH_STRING_SEPARATOR_CHAR = ","
RANGE_CUT_SEPARATOR_CHAR = "-"
SET_CUT_SEPARATOR_CHAR = ";"

CUT_STRING_SEPARATOR = re.compile(r'(?<!\\)\|')
DIMENSION_STRING_SEPARATOR = re.compile(r'(?<!\\):')
PATH_STRING_SEPARATOR = re.compile(r'(?<!\\),')
RANGE_CUT_SEPARATOR = re.compile(r'(?<!\\)-')
SET_CUT_SEPARATOR = re.compile(r'(?<!\\);')

PATH_ELEMENT = r"(?:\\.|[^:;|-])*"

RE_ELEMENT = re.compile(r"^%s$" % PATH_ELEMENT)
RE_POINT = re.compile(r"^%s$" % PATH_ELEMENT)
RE_SET = re.compile(r"^(%s)(;(%s))*$" % (PATH_ELEMENT, PATH_ELEMENT))
RE_RANGE = re.compile(r"^(%s)?-(%s)?$" % (PATH_ELEMENT, PATH_ELEMENT))

"""
point: date:2004
range: date:2004-2010
set: date:2004;2010;2011,04

"""


def cuts_from_string(cube, string, member_converters=None,
                     role_member_converters=None):
    """Return list of cuts specified in `string`. You can use this function to
    parse cuts encoded in a URL.

    Arguments:

    * `string` – string containing the cut descritption (see below)
    * `cube` – cube for which the cuts are being created
    * `member_converters` – callables converting single-item values into paths.
      Keys are dimension names.
    * `role_member_converters` – callables converting single-item values into
      paths. Keys are dimension role names (`Dimension.role`).

    Examples::

        date:2004
        date:2004,1
        date:2004,1|class=5
        date:2004,1,1|category:5,10,12|class:5

    Ranges are in form ``from-to`` with possibility of open range::

        date:2004-2010
        date:2004,5-2010,3
        date:2004,5-2010
        date:2004,5-
        date:-2010

    Sets are in form ``path1;path2;path3`` (none of the paths should be
    empty)::

        date:2004;2010
        date:2004;2005,1;2010,10

    Grammar::

        <list> ::= <cut> | <cut> '|' <list>
        <cut> ::= <dimension> ':' <path>
        <dimension> ::= <identifier>
        <path> ::= <value> | <value> ',' <path>

    The characters '|', ':' and ',' are configured in `CUT_STRING_SEPARATOR`,
    `DIMENSION_STRING_SEPARATOR`, `PATH_STRING_SEPARATOR` respectively.
    """

    if not string:
        return []

    cuts = []

    dim_cuts = CUT_STRING_SEPARATOR.split(string)
    for dim_cut in dim_cuts:
        cut = cut_from_string(dim_cut, cube, member_converters,
                              role_member_converters)
        cuts.append(cut)

    return cuts



def cut_from_string(string, cube=None, member_converters=None,
                    role_member_converters=None):
    """Returns a cut from `string` with dimension `dimension and assumed
    hierarchy `hierarchy`. The string should match one of the following
    patterns:

    * point cut: ``2010,2,4``
    * range cut: ``2010-2012``, ``2010,1-2012,3,5``, ``2010,1-`` (open range)
    * set cut: ``2010;2012``, ``2010,1;2012,3,5;2012,10``

    If the `string` does not match any of the patterns, then ArgumentError
    exception is raised.

    `dimension` can specify a hierarchy in form ``dimension@hierarchy`` such
    as ``date@dqmy``.
    """

    member_converters = member_converters or {}
    role_member_converters = role_member_converters or {}

    dim_hier_pattern = re.compile(r"(?P<invert>!)?"
                                   "(?P<dim>\w+)(@(?P<hier>\w+))?")

    try:
        (dimspec, string) = DIMENSION_STRING_SEPARATOR.split(string)
    except ValueError:
        raise ArgumentError("Wrong dimension cut string: '%s'" % string)

    match = dim_hier_pattern.match(dimspec)

    if match:
        d = match.groupdict()
        invert = (not not d["invert"])
        dimension = d["dim"]
        hierarchy = d["hier"]
    else:
        raise ArgumentError("Dimension spec '%s' does not match "
                            "pattern 'dimension@hierarchy'" % dimspec)

    converter = member_converters.get(dimension)
    if cube:
        role = cube.dimension(dimension).role
        converter = converter or role_member_converters.get(role)
        dimension = cube.dimension(dimension)
        hierarchy = dimension.hierarchy(hierarchy)

    # special case: completely empty string means single path element of ''
    # FIXME: why?
    if string == '':
        return PointCut(dimension, [''], hierarchy, invert)

    elif RE_POINT.match(string):
        path = path_from_string(string)

        if converter:
            path = converter(dimension, hierarchy, path)
        cut = PointCut(dimension, path, hierarchy, invert)

    elif RE_SET.match(string):
        paths = list(map(path_from_string, SET_CUT_SEPARATOR.split(string)))

        if converter:
            converted = []
            for path in paths:
                converted.append(converter(dimension, hierarchy, path))
            paths = converted

        cut = SetCut(dimension, paths, hierarchy, invert)

    elif RE_RANGE.match(string):
        (from_path, to_path) = list(map(path_from_string,
                                        RANGE_CUT_SEPARATOR.split(string)))

        if converter:
            from_path = converter(dimension, hierarchy, from_path)
            to_path = converter(dimension, hierarchy, to_path)

        cut = RangeCut(dimension, from_path, to_path, hierarchy, invert)

    else:
        raise ArgumentError("Unknown cut format (check that keys "
                            "consist only of alphanumeric characters and "
                            "underscore): %s" % string)

    return cut

def cut_from_dict(desc, cube=None):
    """Returns a cut from `desc` dictionary. If `cube` is specified, then the
    dimension is looked up in the cube and set as `Dimension` instances, if
    specified as strings."""

    cut_type = desc["type"].lower()

    dim = desc.get("dimension")

    if dim and cube:
        dim = cube.dimension(dim)

    if cut_type == "point":
        return PointCut(dim, desc.get("path"), desc.get("hierarchy"), desc.get('invert', False))
    elif cut_type == "set":
        return SetCut(dim, desc.get("paths"), desc.get("hierarchy"), desc.get('invert', False))
    elif cut_type == "range":
        return RangeCut(dim, desc.get("from"), desc.get("to"),
                        desc.get("hierarchy"), desc.get('invert', False))
    else:
        raise ArgumentError("Unknown cut type %s" % cut_type)


PATH_PART_ESCAPE_PATTERN = re.compile(r"([\\!|:;,-])")
PATH_PART_UNESCAPE_PATTERN = re.compile(r"\\([\\!|;,-])")


def _path_part_escape(path_part):
    if path_part is None:
        return NULL_PATH_VALUE

    return PATH_PART_ESCAPE_PATTERN.sub(r"\\\1", str(path_part))


def _path_part_unescape(path_part):
    if path_part == NULL_PATH_VALUE:
        return None

    return PATH_PART_UNESCAPE_PATTERN.sub(r"\1", str(path_part))


def string_from_cuts(cuts):
    """Returns a string represeting `cuts`. String can be used in URLs"""
    strings = [compat.to_unicode(cut) for cut in cuts]
    string = CUT_STRING_SEPARATOR_CHAR.join(strings)
    return string


def string_from_path(path):
    """Returns a string representing dimension `path`. If `path` is ``None``
    or empty, then returns empty string. The ptah elements are comma ``,``
    spearated.

    Raises `ValueError` when path elements contain characters that are not
    allowed in path element (alphanumeric and underscore ``_``)."""

    if not path:
        return ""

    path = [_path_part_escape(compat.to_unicode(s)) for s in path]

    if not all(map(RE_ELEMENT.match, path)):
        get_logger().warn("Can not convert path to string: "
                          "keys contain invalid characters "
                          "(should be alpha-numeric or underscore) '%s'" %
                          path)

    string = PATH_STRING_SEPARATOR_CHAR.join(path)
    return string


def string_from_hierarchy(dimension, hierarchy):
    """Returns a string in form ``dimension@hierarchy`` or ``dimension`` if
    `hierarchy` is ``None``"""
    if hierarchy:
        return "%s@%s" % (_path_part_escape(str(dimension)), _path_part_escape(str(hierarchy)))
    else:
        return _path_part_escape(str(dimension))


def path_from_string(string):
    """Returns a dimension point path from `string`. The path elements are
    separated by comma ``,`` character.

    Returns an empty list when string is empty or ``None``.
    """

    if not string:
        return []

    path = PATH_STRING_SEPARATOR.split(string)
    path = [_path_part_unescape(v) for v in path]

    return path


class Cut(object):
    def __init__(self, dimension, hierarchy=None, invert=False,
                 hidden=False):
        """Abstract class for a cell cut."""
        self.dimension = dimension
        self.hierarchy = hierarchy
        self.invert = invert
        self.hidden = hidden

    def to_dict(self):
        """Returns dictionary representation fo the receiver. The keys are:
        `dimension`."""
        d = OrderedDict()

        # Placeholder for 'type' to be at the beginning of the list
        d['type'] = None

        d["dimension"] = str(self.dimension)
        d["hierarchy"] = str(self.hierarchy) if self.hierarchy else None
        d["level_depth"] = self.level_depth()
        d["invert"] = self.invert
        d["hidden"] = self.hidden

        return d

    def level_depth(self):
        """Returns deepest level number. Subclasses should implement this
        method"""
        raise NotImplementedError

    def __repr__(self):
        return str(self.to_dict())


class PointCut(Cut):
    """Object describing way of slicing a cube (cell) through point in a
    dimension"""

    def __init__(self, dimension, path, hierarchy=None, invert=False,
                 hidden=False):
        super(PointCut, self).__init__(dimension, hierarchy, invert, hidden)
        self.path = path

    def to_dict(self):
        """Returns dictionary representation of the receiver. The keys are:
        `dimension`, `type`=``point`` and `path`."""
        d = super(PointCut, self).to_dict()
        d["type"] = "point"
        d["path"] = self.path
        return d

    def level_depth(self):
        """Returns index of deepest level."""
        return len(self.path)

    def __str__(self):
        """Return string representation of point cut, you can use it in
        URLs"""
        path_str = string_from_path(self.path)
        dim_str = string_from_hierarchy(self.dimension, self.hierarchy)
        string = ("!" if self.invert else "") + dim_str + DIMENSION_STRING_SEPARATOR_CHAR + path_str

        return string

    def __eq__(self, other):
        if not isinstance(other, PointCut):
            return False
        if self.dimension != other.dimension:
            return False
        elif self.path != other.path:
            return False
        elif self.invert != other.invert:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)


class RangeCut(Cut):
    """Object describing way of slicing a cube (cell) between two points of a
    dimension that has ordered points. For dimensions with unordered points
    behaviour is unknown."""

    def __init__(self, dimension, from_path, to_path, hierarchy=None,
                 invert=False, hidden=False):
        super(RangeCut, self).__init__(dimension, hierarchy, invert, hidden)
        self.from_path = from_path
        self.to_path = to_path

    def to_dict(self):
        """Returns dictionary representation of the receiver. The keys are:
        `dimension`, `type`=``range``, `from` and `to` paths."""
        d = super(RangeCut, self).to_dict()
        d["type"] = "range"
        d["from"] = self.from_path
        d["to"] = self.to_path
        return d

    def level_depth(self):
        """Returns index of deepest level which is equivalent to the longest
        path."""
        if self.from_path and not self.to_path:
            return len(self.from_path)
        elif not self.from_path and self.to_path:
            return len(self.to_path)
        else:
            return max(len(self.from_path), len(self.to_path))

    def __str__(self):
        """Return string representation of point cut, you can use it in
        URLs"""
        if self.from_path:
            from_path_str = string_from_path(self.from_path)
        else:
            from_path_str = string_from_path([])

        if self.to_path:
            to_path_str = string_from_path(self.to_path)
        else:
            to_path_str = string_from_path([])

        range_str = from_path_str + RANGE_CUT_SEPARATOR_CHAR + to_path_str
        dim_str = string_from_hierarchy(self.dimension, self.hierarchy)
        string = ("!" if self.invert else "") + dim_str + DIMENSION_STRING_SEPARATOR_CHAR + range_str

        return string

    def __eq__(self, other):
        if not isinstance(other, RangeCut):
            return False
        if self.dimension != other.dimension:
            return False
        elif self.from_path != other.from_path:
            return False
        elif self.to_path != other.to_path:
            return False
        elif self.invert != other.invert:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)


class SetCut(Cut):
    """Object describing way of slicing a cube (cell) between two points of a
    dimension that has ordered points. For dimensions with unordered points
    behaviour is unknown."""

    def __init__(self, dimension, paths, hierarchy=None, invert=False,
                 hidden=False):
        super(SetCut, self).__init__(dimension, hierarchy, invert, hidden)
        self.paths = paths

    def to_dict(self):
        """Returns dictionary representation of the receiver. The keys are:
        `dimension`, `type`=``range`` and `set` as a list of paths."""
        d = super(SetCut, self).to_dict()
        d["type"] = "set"
        d["paths"] = self.paths
        return d

    def level_depth(self):
        """Returns index of deepest level which is equivalent to the longest
        path."""
        return max([len(path) for path in self.paths])

    def __str__(self):
        """Return string representation of set cut, you can use it in URLs"""
        path_strings = []
        for path in self.paths:
            path_strings.append(string_from_path(path))

        set_string = SET_CUT_SEPARATOR_CHAR.join(path_strings)
        dim_str = string_from_hierarchy(self.dimension, self.hierarchy)
        string = ("!" if self.invert else "") + dim_str + DIMENSION_STRING_SEPARATOR_CHAR + set_string

        return string

    def __eq__(self, other):
        if not isinstance(other, SetCut):
            return False
        elif self.dimension != other.dimension:
            return False
        elif self.paths != other.paths:
            return False
        elif self.invert != other.invert:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

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
    * `aggregates` – aggregate measures that were selected in aggregation
    * `remainder` - summary of remaining cells (not yet implemented)
    * `levels` – aggregation levels for dimensions that were used to drill-
      down

    .. note::

        Implementors of aggregation browsers should populate `cell`,
        `measures` and `levels` from the aggregate query.

    """
    def __init__(self, cell=None, aggregates=None, drilldown=None):
        super(AggregationResult, self).__init__()
        self.cell = cell
        self.aggregates = aggregates

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

    @property
    def measures(self):
        return self.aggregates

    @measures.setter
    def measures(self, val):
        logger = get_logger()
        logger.warn("AggregationResult.measures is depreciated. Use "
                    "`aggregates`")
        return self.aggregates
        # decorate iterable with calcs if needed

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

        level_key = current_level.key.ref()
        level_label = current_level.label_attribute.ref()

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

CrossTable = namedtuple("CrossTable", ["columns", "rows", "data"])


def cross_table(drilldown, onrows, oncolumns, aggregates):
    """
    Creates a cross table from a drilldown (might be any list of records).
    `onrows` contains list of attribute names to be placed at rows and
    `oncolumns` contains list of attribute names to be placet at columns.
    `aggregates` is a list of aggregate measures to be put into cells.

    Returns a named tuble with attributes:

    * `columns` - labels of columns. The tuples correspond to values of
      attributes in `oncolumns`.
    * `rows` - labels of rows as list of tuples. The tuples correspond to
      values of attributes in `onrows`.
    * `data` - list of aggregated measure data per row. Each row is a list of
      aggregate measure tuples.

    .. warning::

        Experimental implementation. Interface might change - either
        arguments or result object.

    """

    logger = get_logger()
    logger.warn("cross_table() is depreciated, use cross table formatter: "
                "create_formatter(\"cross_table\", ...)")
    matrix = {}
    row_hdrs = []
    column_hdrs = []

    for record in drilldown:
        hrow = tuple(record[f] for f in onrows)
        hcol = tuple(record[f] for f in oncolumns)

        if not hrow in row_hdrs:
            row_hdrs.append(hrow)
        if not hcol in column_hdrs:
            column_hdrs.append(hcol)

        matrix[(hrow, hcol)] = tuple(record[m] for m in aggregates)

    data = []
    for hrow in row_hdrs:
        row = [matrix.get((hrow, hcol)) for hcol in column_hdrs]
        data.append(row)

    return CrossTable(column_hdrs, row_hdrs, data)


def string_to_drilldown(astring):
    """Converts `astring` into a drilldown tuple (`dimension`, `hierarchy`,
    `level`). The string should have a format:
    ``dimension@hierarchy:level``. Hierarchy and level are optional.

    Raises `ArgumentError` when `astring` does not match expected pattern.
    """

    if not astring:
        raise ArgumentError("Drilldown string should not be empty")

    ident = r"[\w\d_]"
    pattern = r"(?P<dim>%s+)(@(?P<hier>%s+))?(:(?P<level>%s+))?" % (ident,
                                                                    ident,
                                                                    ident)
    match = re.match(pattern, astring)

    if match:
        d = match.groupdict()
        return (d["dim"], d["hier"], d["level"])
    else:
        raise ArgumentError("String '%s' does not match drilldown level "
                            "pattern 'dimension@hierarchy:level'" % astring)


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

        return levels

    def high_cardinality_levels(self, cell):
        """Returns list of levels in the drilldown that are of high
        cardinality and there is no cut for that level in the `cell`."""

        for item in self.drilldown:
            dim, hier, levels = item[0:3]
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

    def all_attributes(self):
        """Returns attributes of all levels in the drilldown. Order is by the
        drilldown item, then by the levels and finally by the attribute in the
        level."""
        attributes = []
        for item in self.drilldown:
            for level in item.levels:
                attributes += level.attributes

        return attributes

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
def levels_from_drilldown(cell, drilldown, simplify=True):
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

    If `simplify` is `True` then dimension references are simplified for flat
    dimensions without details. Otherwise full dimension attribute reference
    will be used as `level_key`.

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
            obj = string_to_drilldown(obj)
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
        keys = [level.key.ref(simplify=simplify) for level in levels]
        result.append(DrilldownItem(dim, hier, levels, keys))

    return result

