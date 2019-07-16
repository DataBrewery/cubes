# -*- coding: utf-8 -*-

from typing import Mapping  # Collection,
from typing import (
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Set,
    Sized,
    Tuple,
    Union,
    cast,
)

from ..errors import ArgumentError, HierarchyError
from ..metadata import (
    Attribute,
    Cube,
    Dimension,
    Hierarchy,
    Level,
    string_to_dimension_level,
)
from .cells import Cell, Cut, PointCut, SetCut, cuts_from_string
from .constants import SPLIT_DIMENSION_NAME

# FIXME: Update afetr Python 3.6.1
Collection = List

__all__ = ["Drilldown", "DrilldownItem", "levels_from_drilldown"]


class DrilldownItem(NamedTuple):
    dimension: Dimension
    hierarchy: Hierarchy
    levels: List[Level]
    keys: List[str]


# FIXME: This needs to go away.
_DrilldownType = Union[
    "Drilldown",
    List[
        Union[
            str,
            Dimension,
            DrilldownItem,
            Tuple[Union[Dimension, str], Union[Hierarchy, str], Union[Level, str]],
        ]
    ],
]


class Drilldown(Iterable, Sized):

    drilldown: List[DrilldownItem]
    cube: Cube
    dimensions: List[Dimension]
    _contained_dimensions: Set[str]

    def __init__(self, cube: Cube, items: _DrilldownType = None) -> None:
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

        self.cube = cube
        self.drilldown = levels_from_drilldown(cube, items)
        self.dimensions = []
        self._contained_dimensions = set()

        for dd in self.drilldown:
            self.dimensions.append(dd.dimension)
            self._contained_dimensions.add(dd.dimension.name)

    def __str__(self) -> str:
        return ",".join(self.items_as_strings())

    def items_as_strings(self) -> List[str]:
        """Returns drilldown items as strings: ``dimension@hierarchy:level``.
        If hierarchy is dimension's default hierarchy, then it is not included
        in the string: ``dimension:level``"""

        strings = []

        for item in self.drilldown:
            if item.hierarchy != item.dimension.hierarchy():
                hierstr = "@%s" % str(item.hierarchy)
            else:
                hierstr = ""

            ddstr = "{}{}:{}".format(item.dimension.name, hierstr, item.levels[-1].name)
            strings.append(ddstr)

        return strings

    def drilldown_for_dimension(
        self, dim: Union[str, Dimension]
    ) -> List[DrilldownItem]:
        """Returns drilldown items for dimension `dim`."""
        items = []
        dimname = str(dim)
        for item in self.drilldown:
            if str(item.dimension) == dimname:
                items.append(item)

        return items

    def __getitem__(self, key: int) -> DrilldownItem:
        return self.drilldown[key]

    def deepest_levels(self) -> List[Tuple[Dimension, Hierarchy, Level]]:
        """Returns a list of tuples: (`dimension`, `hierarchy`, `level`) where
        `level` is the deepest level drilled down to.

        This method is currently used for preparing the periods-to-date
        conditions.
        """

        levels = []

        for dditem in self.drilldown:
            item = (dditem.dimension, dditem.hierarchy, dditem.levels[-1])
            levels.append(item)

        return levels

    # This is resurrected from Cell in which cube was removed
    def _cell_contains_level(
        self,
        cell: Cell,
        dimension: Union[Dimension, str],
        level: str,
        hierarchy: str = None,
    ) -> bool:
        """Returns `True` if one of the cuts contains `level` of dimension
        `dim`. If `hierarchy` is not specified, then dimension's default
        hierarchy is used."""

        dim = self.cube.dimension(dimension)
        hierarchy_obj = dim.hierarchy(hierarchy)

        for cut in cell.cuts_for_dimension(dim.name):
            if cut.hierarchy != hierarchy_obj.name:
                continue
            if isinstance(cut, PointCut):
                if level in hierarchy_obj.levels_for_depth(len(cut.path)):
                    return True
            if isinstance(cut, SetCut):
                for path in cut.paths:
                    if level in hierarchy_obj.levels_for_depth(len(path)):
                        return True
        return False

    def high_cardinality_levels(self, cell: Cell) -> List[Level]:
        """Returns list of levels in the drilldown that are of high
        cardinality and there is no cut for that level in the `cell`."""

        not_contained: List[Level] = []

        for item in self.drilldown:
            dim, hier, _ = item[0:3]

            # TODO: Replace with enums
            for level in item.levels:
                contains_level = self._cell_contains_level(
                    cell, dim.name, level.name, hier.name
                )

                if (
                    level.cardinality == "high" or dim.cardinality == "high"
                ) and contains_level:
                    not_contained.append(level)

        return not_contained

    def result_levels(self, include_split: bool = False) -> Mapping[str, List[str]]:
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
                dim_key = f"{dim.name}@{hier.name}"

            result[dim_key] = [str(level) for level in levels]

        if include_split:
            result[SPLIT_DIMENSION_NAME] = [SPLIT_DIMENSION_NAME]

        return result

    @property
    def key_attributes(self) -> List[Attribute]:
        """Returns only key attributes of all levels in the drilldown. Order
        is by the drilldown item, then by the levels and finally by the
        attribute in the level.

        .. versionadded:: 1.1
        """
        attributes: List[Attribute] = []
        for item in self.drilldown:
            attributes += [level.key for level in item.levels]

        return attributes

    @property
    def all_attributes(self) -> Collection[Attribute]:
        """Returns attributes of all levels in the drilldown. Order is by the
        drilldown item, then by the levels and finally by the attribute in the
        level."""
        attributes: List[Attribute] = []
        for item in self.drilldown:
            for level in item.levels:
                attributes += level.attributes

        return attributes

    # FIXME: [typing] See #395
    @property
    def natural_order(self) -> List[Tuple[Attribute, str]]:
        """Return a natural order for the drill-down. This order can be merged
        with user-specified order. Returns a list of tuples:
        (`attribute_name`, `order`)."""

        order = []

        for item in self.drilldown:
            for level in item.levels:
                lvl_attr = level.order_attribute or level.key
                lvl_order = level.order or "asc"
                order.append((lvl_attr, lvl_order))

        return order

    def __len__(self) -> int:
        return len(self.drilldown)

    def __iter__(self) -> Iterator[DrilldownItem]:
        return self.drilldown.__iter__()

    def __nonzero__(self) -> bool:
        return len(self.drilldown) > 0


# TODO: move this to Drilldown
def levels_from_drilldown(
    cube: Cube, drilldown: Optional[_DrilldownType]
) -> List[DrilldownItem]:
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

    if drilldown is None:
        return []

    result = []

    for obj in drilldown:
        if isinstance(obj, str):
            obj = string_to_dimension_level(obj)
        elif isinstance(obj, DrilldownItem):
            obj = (obj.dimension, obj.hierarchy, obj.levels[-1])
        elif isinstance(obj, Dimension):
            obj = (obj, obj.hierarchy(), obj.hierarchy().levels[-1])
        elif len(obj) != 3:
            raise ArgumentError(
                f"Drilldown item should be either a string "
                f"or a tuple of three elements. Is: {obj}"
            )

        dim_any, hier_any, level_any = obj

        dim: Dimension = cube.dimension(dim_any)
        hier: Hierarchy = dim.hierarchy(hier_any)

        level: Level

        if level_any:
            index = hier.level_index(str(level_any))
            levels = hier.levels[: index + 1]
        else:
            levels = hier.levels[:1]

        keys = [level.key.ref for level in levels]
        result.append(DrilldownItem(dim, hier, levels, keys))

    return result
