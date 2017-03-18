# -*- coding: utf-8 -*-

from typing import (
        Any,
        Iterable,
        Iterator,
        List,
        Mapping,
        NamedTuple,
        Optional,
        cast,
    )

# FIXME: [typing] Python 3.6.1
Collection = List

from ..types import JSONType, _RecordType

from ..metadata import (
        Cube,
        Dimension,
        Hierarchy,
        HierarchyPath,
        Level,
        MeasureAggregate,
    )

from ..query.cells import Cell, PointCut
from ..query.drilldown import Drilldown

from .statutils import _CalculatorFunction
from ..common import IgnoringDictionary

__all__ = [
    "AggregationResult",
    "Facts",
    "TableRow",
]


class TableRow(NamedTuple):
    key: Any
    label: Any
    path: Any
    is_base: bool
    record: Any


class Facts(Iterable):
    facts: Iterable[_RecordType]
    attributes: List[str]

    def __init__(self,
            facts: Iterable[_RecordType],
            attributes: List[str]) -> None:
        """A facts iterator object returned by the browser's `facts()`
        method."""

        self.facts = facts or []
        self.attributes = attributes

    def __iter__(self) -> Iterator[_RecordType]:
        return iter(self.facts)


class CalculatedResultIterator(Iterable):
    """
    Iterator that decorates data items
    """
    calculators: Collection[_CalculatorFunction]
    iterator: Iterator[_RecordType]

    def __init__(self,
            calculators: Collection[_CalculatorFunction],
            iterator: Iterator[_RecordType]) -> None:
        self.calculators = calculators
        self.iterator = iterator

    def __iter__(self) -> Iterator[_RecordType]:
        return cast(Iterator[_RecordType], self)

    def __next__(self) -> _RecordType:
        # Apply calculators to the result record
        item = next(self.iterator)
        for calc in self.calculators:
            calc(item)
        return item

    next = __next__


class AggregationResult(Iterable):
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

    # TODO: This should be List[Cube] for drill-across
    cube: Cube
    cell: Cell
    aggregates: Collection[MeasureAggregate]
    calculators: List[_CalculatorFunction]
    # FIXME: [typing] See #410
    summary: _RecordType
    drilldown: Optional[Drilldown]
    levels: Optional[Mapping[str, List[str]]]
    total_cell_count: Optional[int]
    remainder: JSONType
    labels: Optional[Collection[str]]
    # FIXME: [typing] Fix the type
    _cells: Iterable[_RecordType]

    def __init__(self,
            cube: Cube,
            cell: Cell,
            cells: Iterable[_RecordType],
            labels: Optional[Collection[str]]=None,
            summary: Optional[_RecordType]=None,
            aggregates: Collection[MeasureAggregate]=None,
            drilldown: Drilldown=None,
            levels: Optional[Mapping[str, List[str]]]=None,
            total_cell_count: Optional[int]=None,
            remainder: Optional[JSONType]=None,
            has_split: bool=False) -> None:
        """Create an aggergation result object. `cell` – a :class:`cubes.Cell`
        object used for this aggregation, `aggregates` – list of aggregate
        objects selected for this a aggregation, `drilldown` – a
        :class:`cubes.Drilldown` object representing list of dimensions and
        hierarchies the result is drilled-down by, `has_split` – flag whether
        the result has a split dimension."""

        self.cube = cube
        self.cell = cell

        # Note: aggregates HAS to be a list of Aggregate objects, not just
        # list of strings
        self.aggregates = aggregates or []

        self.drilldown = drilldown

        # TODO: Experimental, undocumented
        if self.drilldown is not None:
            attrs = [attr.ref for attr in self.drilldown.all_attributes]
            self.attributes = attrs
        else:
            self.attributes = []

        self.has_split = has_split

        if drilldown:
            self.levels = drilldown.result_levels()
        else:
            self.levels = None

        self.summary = summary or {}

        self.total_cell_count = total_cell_count
        self.remainder = remainder or {}
        self.labels = labels or []
        self.calculators = []

        # Initialize last
        self._cells = []
        self.cells = cells


    @property
    def cells(self) -> Iterable[_RecordType]:
        return self._cells

    @cells.setter
    def cells(self, val: Iterable[_RecordType]) -> None:
        # decorate iterable with calcs if needed
        if self.calculators:
            val = CalculatedResultIterator(self.calculators, iter(val))
        self._cells = val

    def to_dict(self) -> JSONType:
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

    def table_rows(self,
            dimension_name: str,
            depth: int=None,
            hierarchy: Hierarchy=None) -> Iterator[TableRow]:
        """Returns iterator of drilled-down rows which yields a named tuple
        with named attributes: (key, label, path, record). `depth` is last
        level of interest. If not specified (set to ``None``) then deepest
        level for `dimension` is used.

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

        dimension: Dimension

        cut: Optional[PointCut]
        cut = self.cell.point_cut_for_dimension(dimension_name)

        path: HierarchyPath
        if cut is not None:
            path = cut.path
        else:
            path = []

        # FIXME: use hierarchy from cut (when implemented)
        dimension = self.cube.dimension(dimension_name)
        hierarchy = dimension.hierarchy(hierarchy)

        if self.levels:
            # Convert "levels" to a dictionary:
            # all_levels = dict((dim, levels) for dim, levels in self.levels)
            dim_levels = self.levels.get(dimension.name, [])
            is_base = len(dim_levels) >= len(hierarchy)
        else:
            is_base = len(hierarchy) == 1

        if depth:
            current_level = hierarchy.levels[depth - 1]
        else:
            levels = hierarchy.levels_for_depth(len(path), drilldown=True)
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

    def __iter__(self) -> Iterator[_RecordType]:
        """Return cells as iterator"""
        return iter(self.cells)

    def cached(self) -> "AggregationResult":
        """Return shallow copy of the receiver with cached cells. If cells are
        an iterator, they are all fetched in a list.

        .. warning::

            This might be expensive for large results.
        """
        result = AggregationResult(
            cube=self.cube,
            cell=self.cell,
            aggregates=self.aggregates,
            summary=self.summary,
            total_cell_count=self.total_cell_count,
            remainder=self.remainder,
            labels=self.labels,
            drilldown=self.drilldown,
            has_split=self.has_split,
            levels=self.levels,
            # Cache cells from an iterator
            cells=list(self.cells)
        )

        return result
