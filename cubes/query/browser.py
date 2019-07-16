# -*- coding: utf-8 -*-

from collections import namedtuple
from enum import Enum
from typing import (
    Any,
    Collection,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    NamedTuple,
    Optional,
    Set,
    Sized,
    Tuple,
    Union,
    cast,
)

from ..calendar import Calendar, CalendarMemberConverter
from ..common import IgnoringDictionary
from ..errors import ArgumentError, HierarchyError, InternalError, NoSuchAttributeError
from ..ext import Extensible
from ..logging import get_logger
from ..metadata import (
    Attribute,
    AttributeBase,
    Cube,
    Dimension,
    Hierarchy,
    HierarchyPath,
    Level,
    Measure,
    MeasureAggregate,
    string_to_dimension_level,
)
from ..settings import SettingsDict
from ..stores import Store
from ..types import JSONType, ValueType, _RecordType
from .cells import Cell, Cut, PointCut, RangeCut, SetCut, cuts_from_string
from .constants import NULL_PATH_VALUE, SPLIT_DIMENSION_NAME
from .drilldown import Drilldown, DrilldownItem, _DrilldownType
from .result import AggregationResult, Facts
from .statutils import (
    _CalculatorFunction,
    available_calculators,
    calculators_for_aggregates,
)

__all__ = ["AggregationBrowser"]


# Order can be: `name` or (`name`, `direction`)
_OrderType = Tuple[AttributeBase, str]
_OrderArgType = Union[str, Union[_OrderType, Tuple[str, str]]]
_ReportResult = Union[AggregationResult, Facts, JSONType, List[JSONType]]


class BrowserFeatureAction(Enum):
    aggregate = 1
    fact = 2
    facts = 3
    members = 4
    cell = 5


class BrowserFeatures:
    actions: Collection[BrowserFeatureAction]
    aggregate_functions: Collection[str]
    post_aggregate_functions: Collection[str]

    def __init__(
        self,
        actions: Optional[Collection[BrowserFeatureAction]] = None,
        aggregate_functions: Optional[Collection[str]] = None,
        post_aggregate_functions: Optional[Collection[str]] = None,
    ) -> None:
        self.actions = actions or []
        self.aggregate_functions = aggregate_functions or []
        self.post_aggregate_functions = post_aggregate_functions or []

    @classmethod
    def from_dict(cls, data: JSONType) -> "BrowserFeatures":
        actions_names: List[str] = data.get("actions")
        aggregate_functions: List[str] = data.get("aggregate_functions")
        post_aggregate_functions: List[str] = data.get("post_aggregate_functions")

        try:
            actions = [BrowserFeatureAction[action] for action in actions_names]
        except KeyError:
            raise InternalError("Some actions are not valid.")

        return BrowserFeatures(
            actions=actions,
            aggregate_functions=aggregate_functions,
            post_aggregate_functions=post_aggregate_functions,
        )

    def to_dict(self) -> JSONType:
        result: JSONType = {}
        if self.actions:
            result["actions"] = [action.name for action in self.actions]
        if self.aggregate_functions:
            result["aggregate_functions"] = self.aggregate_functions
        if self.post_aggregate_functions:
            result["post_aggregate_functions"] = self.post_aggregate_functions

        return result


class AggregationBrowser(Extensible, abstract=True):
    """Class for browsing data cube aggregations.

    :Attributes:
      * `cube` - cube for browsing
    """

    __extension_type__ = "browser"
    __extension_suffix__ = "Browser"

    # Functions that are supported by this browser
    builtin_functions: List[str] = []

    cube: Cube
    # TODO: Review when store can be optional
    store: Optional[Store]
    calendar: Optional[Calendar]
    locale: Optional[str]

    def __init__(
        self,
        cube: Cube,
        store: Optional[Store] = None,
        locale: Optional[str] = None,
        calendar: Optional[Calendar] = None,
    ) -> None:
        """Creates and initializes the aggregation browser.

        Subclasses should override this method.
        """
        super().__init__()

        assert cube is not None, "No cube given for aggregation browser"

        self.cube = cube
        self.store = store
        self.locale = locale
        self.calendar = None

    # TODO: Make this an explicit structure
    def features(self) -> BrowserFeatures:
        """Returns a dictionary of available features for the browsed cube.
        Default implementation returns an empty dictionary.

        Standard keys that might be present:

        * `actions` – list of actions that can be done with the cube, such as
          ``facts``, ``aggregate``, ``members``, ...
        * `post_aggregate_functions` – list of aggregates that are computed
          after the result is fetched from the source (not natively).

        Subclasses are advised to override this method.
        """
        return BrowserFeatures()

    # TODO: No *options
    def aggregate(
        self,
        cell: Cell = None,
        aggregates: List[str] = None,
        drilldown: _DrilldownType = None,
        split: Cell = None,
        order: Optional[Collection[_OrderArgType]] = None,
        page: int = None,
        page_size: int = None,
        **options: Any,
    ) -> AggregationResult:

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

        prepared_aggregates: Collection[MeasureAggregate]
        prepared_aggregates = self.prepare_aggregates(aggregates)
        prepared_order: Collection[_OrderType]
        prepared_order = self.prepare_order(order, is_aggregate=True)

        converters = {"time": CalendarMemberConverter(self.calendar)}

        if cell is None:
            cell = Cell()
        elif isinstance(cell, str):
            cuts = cuts_from_string(self.cube, cell, role_member_converters=converters)
            cell = Cell(cuts)

        if isinstance(split, str):
            cuts = cuts_from_string(self.cube, split, role_member_converters=converters)
            split = Cell(cuts)

        drilldown = Drilldown(self.cube, items=drilldown)

        result = self.provide_aggregate(
            cell,
            aggregates=prepared_aggregates,
            drilldown=drilldown,
            split=split,
            order=prepared_order,
            page=page,
            page_size=page_size,
        )

        #
        # Find post-aggregation calculations and decorate the result
        #
        calculated_aggs = [
            agg
            for agg in prepared_aggregates
            if agg.function and not self.is_builtin_function(agg.function)
        ]

        result.calculators = calculators_for_aggregates(
            self.cube, calculated_aggs, drilldown, split
        )

        # Do calculated measures on summary if no drilldown or split
        if result.summary:
            for calc in result.calculators:
                calc(result.summary)

        return result

    def provide_aggregate(
        self,
        cell: Cell,
        aggregates: Collection[MeasureAggregate],
        drilldown: Drilldown,
        split: Optional[Cell] = None,
        order: Optional[Collection[_OrderType]] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> AggregationResult:
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
        raise NotImplementedError(
            "{} does not provide aggregate functionality.".format(str(type(self)))
        )

    def prepare_aggregates(
        self, aggregates: List[Any] = None
    ) -> List[MeasureAggregate]:
        """Prepares the aggregate list for aggregatios. `aggregates` might be a
        list of aggregate names or `MeasureAggregate` objects.

        Aggregates that are used in post-aggregation calculations are included
        in the result. This method is using `is_builtin_function()` to check
        whether the aggregate is native to the backend or not.

        If no aggregates are specified then all cube's aggregates are returned.
        """

        # Coalesce measures - make sure that they are Attribute objects, not
        # strings. Strings are converted to corresponding Cube measure
        # attributes
        # TODO: perhaps we might merge (without duplicates)

        prepared: List[MeasureAggregate]

        if aggregates:
            prepared = [self.cube.aggregate(agg) for agg in aggregates]
        else:
            prepared = self.cube.aggregates

        seen: Set[str]
        seen = {a.name for a in prepared}

        dependencies: List[MeasureAggregate] = []

        # Resolve aggregate dependencies for non-builtin functions:
        # TODO: This is not sufficient, we need to resolve the expression as
        # well
        for agg in prepared:
            # If aggregate has a measure specified and the function is
            # post-aggregate function (not backend built-in) and we haven't
            # seen the measure yet, then the measure is considered to be
            # another aggregate measure and therefore we need to include it in
            # the queried aggregates.
            if (
                agg.measure
                and agg.function is not None
                and not self.is_builtin_function(agg.function)
                and agg.measure not in seen
            ):

                seen.add(agg.measure)
                aggregate = self.cube.aggregate(agg.measure)
                dependencies.append(aggregate)

        return prepared + dependencies

    def prepare_order(
        self, order: Optional[Collection[_OrderArgType]], is_aggregate: bool = False
    ) -> Collection[_OrderType]:
        """Prepares an order list.

        Returns list of tuples (`attribute`, `order_direction`).
        `attribute` is cube's attribute object.
        """

        order = order or []
        new_order: List[_OrderType] = []

        for item in order:
            attribute: Optional[AttributeBase] = None

            if isinstance(item, str):
                name, direction = (item, None)
            else:
                name, direction = item[0:2]

            if is_aggregate:
                function = None
                try:
                    attribute = self.cube.aggregate(name)
                    function = attribute.function
                except NoSuchAttributeError:
                    attribute = self.cube.attribute(name)

                # FIXME: This is not good, has to be recursive.
                # FIXME: This should be resolved before calling this method.
                if function and not self.is_builtin_function(function):
                    # TODO: Temporary solution: get the original measure instead

                    measure: AttributeBase
                    try:
                        name = str(cast(MeasureAggregate, attribute).measure)
                        measure = self.cube.aggregate(name)
                    except NoSuchAttributeError:
                        measure = self.cube.measure(name)

                    attribute = measure
            else:
                attribute = self.cube.attribute(name)

            if attribute:
                new_order.append((attribute, direction))

        return new_order

    def assert_low_cardinality(self, cell: Cell, drilldown: "Drilldown") -> None:
        """Raises `ArgumentError` when there is drilldown through high
        cardinality dimension or level and there is no condition in the cell
        for the level."""

        hc_levels = drilldown.high_cardinality_levels(cell)
        if hc_levels:
            names = [str(level) for level in hc_levels]
            names_str = ", ".join(names)
            raise ArgumentError(
                f"Can not drilldown on high-cardinality levels"
                f"({names_str}) without including both "
                f"page_size and page arguments, or else a "
                f"point/set cut on the level"
            )

    def is_builtin_function(self, function_name: str) -> bool:
        """Returns `True` if function `function_name` is bult-in. Returns
        `False` if the browser can not compute the function and post-
        aggregation calculation should be used.

        Default implementation returns `True` for all unctions except those in
        :func:`available_calculators`. Subclasses are reommended to override
        this method if they have their own built-in version of the aggregate
        functions.
        """

        return function_name in available_calculators()

    def facts(
        self,
        cell: Cell = None,
        fields: Collection[AttributeBase] = None,
        order: List[_OrderArgType] = None,
        page: int = None,
        page_size: int = None,
        fact_list: List[ValueType] = None,
    ) -> Facts:
        """Return an iterable object with of all facts within cell. `fields` is
        list of fields to be considered in the output.

        Subclasses overriding this method sould return a :class:`Facts`
        object and set it's `attributes` to the list of selected
        attributes.
        """
        raise NotImplementedError(
            "{} does not provide facts functionality.".format(str(type(self)))
        )

    def fact(
        self, key: ValueType, fields: Collection[AttributeBase] = None
    ) -> Optional[_RecordType]:
        """Returns a single fact from cube specified by fact key `key`"""
        raise NotImplementedError(
            "{} does not provide fact functionality.".format(str(type(self)))
        )

    def members(
        self,
        cell: Cell,
        dimension: Dimension,
        depth: int = None,
        level: Level = None,
        hierarchy: Hierarchy = None,
        attributes: Collection[str] = None,
        order: Optional[Collection[_OrderArgType]] = None,
        page: int = None,
        page_size: int = None,
        **options: Any,
    ) -> Iterable[_RecordType]:
        """Return members of `dimension` with level depth `depth`.

        If `depth` is ``None``, all levels are returned. If no
        `hierarchy` is specified, then default dimension hierarchy is
        used.
        """
        prepared_order = self.prepare_order(order, is_aggregate=False)

        if cell is None:
            cell = Cell()

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
        elif level:
            index = hierarchy.level_index(level.name)
            levels = hierarchy.levels_for_depth(index + 1)

        attribute_objs: Collection[AttributeBase]
        if attributes is not None:
            attribute_objs = self.cube.all_fact_attributes
        else:
            attribute_objs = self.cube.get_attributes(attributes)

        result = self.provide_members(
            cell,
            dimension=dimension,
            hierarchy=hierarchy,
            levels=levels,
            attributes=attribute_objs,
            order=prepared_order,
            page=page,
            page_size=page_size,
            **options,
        )
        return result

    def provide_members(
        self,
        cell: Cell,
        dimension: Dimension,
        depth: int = None,
        hierarchy: Hierarchy = None,
        levels: Collection[Level] = None,
        attributes: Collection[AttributeBase] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        order: Optional[Collection[_OrderType]] = None,
    ) -> Iterable[_RecordType]:
        raise NotImplementedError(
            "{} does not provide members functionality.".format(str(type(self)))
        )

    # FIXME: [important] Properly annotate this one
    def test(self, aggregate: bool = False) -> None:
        """Tests whether the cube can be used.

        Refer to the backend's documentation for more information about
        what is being tested.
        """
        raise NotImplementedError(
            "{} does not provide test functionality.".format(str(type(self)))
        )

    # FIXME: Create a special "report query" object
    def report(self, cell: Cell, queries: JSONType) -> Dict[str, _ReportResult]:
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

        # FIXME: This type is very unintuitive
        result: _ReportResult
        report_result: Dict[str, _ReportResult] = {}

        for result_name, query in queries.items():
            query_type = query.get("query")
            if not query_type:
                raise ArgumentError("No report query for '%s'" % result_name)

            # FIXME: add: cell = query.get("cell")

            args = dict(query)
            del args["query"]

            # Note: we do not just convert name into function from symbol for possible
            # future more fine-tuning of queries as strings

            # FIXME: [2.0] dimension was removed from cell, the following code
            # does not work any more.
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
                raise ArgumentError(
                    f"Unknown report query '{query_type}' for '{result_name}'"
                )

            report_result[result_name] = result

        return report_result

    def cell_details(
        self, cell: Cell = None, dimension: Union[str, Dimension] = None
    ) -> List[JSONType]:
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
            cuts = [cut for cut in cell.cuts if cut.dimension == str(dimension)]
        else:
            cuts = cell.cuts

        details = [self.cut_details(cut) for cut in cuts]

        return details

    # TODO: Make return type to be JSONType
    def cut_details(self, cut: Cut) -> Any:
        """Gets details for a `cut` which should be a `Cut` instance.

        * `PointCut` - all attributes for each level in the path
        * `SetCut` - list of `PointCut` results, one per path in the set
        * `RangeCut` - `PointCut`-like results for lower range (from) and
          upper range (to)
        """

        details: Any

        dimension = self.cube.dimension(cut.dimension)

        if isinstance(cut, PointCut):
            details = self._path_details(dimension, cut.path, cut.hierarchy)

        elif isinstance(cut, SetCut):
            details = [
                self._path_details(dimension, path, cut.hierarchy) for path in cut.paths
            ]

        elif isinstance(cut, RangeCut):
            details = {
                "from": self._path_details(
                    dimension=dimension,
                    path=cut.from_path or [],
                    hierarchy=cut.hierarchy,
                ),
                "to": self._path_details(
                    dimension=dimension, path=cut.to_path or [], hierarchy=cut.hierarchy
                ),
            }

        else:
            raise Exception("Unknown cut type %s" % cut)

        return details

    # FIXME: [typing] fix the return type to RecordType, see #410
    def _path_details(
        self,
        dimension: Dimension,
        path: List[str],
        hierarchy: Union[str, Hierarchy] = None,
    ) -> Optional[List[Dict[str, Optional[str]]]]:
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

        result = []
        for level in hierarchy.levels_for_depth(len(path)):
            item = {a.ref: details.get(a.ref) for a in level.attributes}
            item["_key"] = details.get(level.key.ref)
            item["_label"] = details.get(level.label_attribute.ref)
            result.append(item)

        return result

    # TODO: [typing] Improve the return type
    def path_details(
        self, dimension: Dimension, path: HierarchyPath, hierarchy: Hierarchy
    ) -> Optional[_RecordType]:
        """Returns empty path details.

        Default fall-back for backends that do not support the path
        details. The level key and label are the same derived from the
        key.
        """

        detail: Dict[str, Optional[str]] = {}
        for level, key in zip(hierarchy.levels, path):
            for attr in level.attributes:
                if attr == level.key or attr == level.label_attribute:
                    detail[attr.ref] = key
                else:
                    detail[attr.ref] = None

        return detail
