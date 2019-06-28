# -*- coding: utf-8 -*-

import copy
import re

from collections import OrderedDict
from typing import (
        Any,
        Callable,
        Collection,
        Dict,
        List,
        Optional,
        Set,
        Tuple,
        Union,
        cast,
    )

from ..types import JSONType
from ..errors import ArgumentError, CubesError
from ..metadata.dimension import Dimension, Hierarchy, Level, HierarchyPath
from ..metadata.attributes import Attribute
from ..metadata.cube import Cube
from ..logging import get_logger


__all__ = [
    "Cell",
    "Cut",
    "PointCut",
    "RangeCut",
    "SetCut",

    "cuts_from_string",
    "string_from_cuts",
    "string_from_path",
    "string_from_hierarchy",
    "path_from_string",
    "cut_from_string",
    "cut_from_dict",
]


NULL_PATH_VALUE = '__null__'


# Function that takes dimension hierarchy path and returns a member value
MemberConverter = Callable[[Dimension, Hierarchy, HierarchyPath], HierarchyPath]


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
RE_SET = re.compile(fr"^({PATH_ELEMENT})(;({PATH_ELEMENT}))*$")
RE_RANGE = re.compile(fr"^({PATH_ELEMENT})?-({PATH_ELEMENT})?$")

"""
point: date:2004
range: date:2004-2010
set: date:2004;2010;2011,04

"""

class Cut:

    dimension: str
    hierarchy: Optional[str]
    invert: bool
    hidden: bool

    def __init__(self,
            dimension: str,
            hierarchy: str=None,
            invert: bool=False,
            hidden: bool=False) -> None:
        """Abstract class for a cell cut."""
        self.dimension = dimension
        self.hierarchy = hierarchy
        self.invert = invert
        self.hidden = hidden

    def to_dict(self) -> JSONType:
        """Returns dictionary representation fo the receiver. The keys are:
        `dimension`."""
        d: JSONType = OrderedDict()

        # Placeholder for 'type' to be at the beginning of the list
        d['type'] = None

        d["dimension"] = self.dimension
        d["hierarchy"] = self.hierarchy if self.hierarchy else None
        d["level_depth"] = self.level_depth()
        d["invert"] = self.invert
        d["hidden"] = self.hidden

        return d

    def level_depth(self) -> int:
        """Returns deepest level number. Subclasses should implement this
        method"""
        raise NotImplementedError

    def __repr__(self) -> str:
        return str(self.to_dict())


class PointCut(Cut):
    """Object describing way of slicing a cube (cell) through point in a
    dimension"""

    path: HierarchyPath

    def __init__(self,
            dimension: str,
            path: HierarchyPath,
            hierarchy: str=None,
            invert: bool=False,
            hidden: bool=False) -> None:
        super().__init__(dimension, hierarchy, invert, hidden)
        self.path = path

    def to_dict(self) -> JSONType:
        """Returns dictionary representation of the receiver. The keys are:
        `dimension`, `type`=``point`` and `path`."""
        d = super().to_dict()
        d["type"] = "point"
        d["path"] = self.path
        return d

    def level_depth(self) -> int:
        """Returns index of deepest level."""
        return len(self.path)

    def __str__(self) -> str:
        """Return string representation of point cut, you can use it in
        URLs"""
        path_str = string_from_path(self.path)
        dim_str = string_from_hierarchy(self.dimension, self.hierarchy)
        string = ("!" if self.invert else "") + dim_str + DIMENSION_STRING_SEPARATOR_CHAR + path_str

        return string

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PointCut):
            return False
        if self.dimension != other.dimension:
            return False
        elif self.path != other.path:
            return False
        elif self.invert != other.invert:
            return False
        return True

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)


class RangeCut(Cut):
    """Object describing way of slicing a cube (cell) between two points of a
    dimension that has ordered points. For dimensions with unordered points
    behaviour is unknown."""

    from_path: Optional[HierarchyPath]
    to_path: Optional[HierarchyPath]

    def __init__(self,
            dimension: str,
            from_path: Optional[HierarchyPath],
            to_path: Optional[HierarchyPath],
            hierarchy: str=None,
            invert: bool=False,
            hidden: bool=False) -> None:
        super().__init__(dimension, hierarchy, invert, hidden)
        self.from_path = from_path
        self.to_path = to_path

    def to_dict(self) -> JSONType:
        """Returns dictionary representation of the receiver. The keys are:
        `dimension`, `type`=``range``, `from` and `to` paths."""
        d = super().to_dict()
        d["type"] = "range"
        d["from"] = self.from_path
        d["to"] = self.to_path
        return d

    def level_depth(self) -> int:
        """Returns index of deepest level which is equivalent to the longest
        path."""
        depth: int = 0

        if self.from_path and not self.to_path:
            depth = len(self.from_path)
        elif not self.from_path and self.to_path:
            depth = len(self.to_path)
        elif self.from_path and self.to_path:
            depth = max(len(self.from_path), len(self.to_path))

        return depth

    def __str__(self) -> str:
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
        string = ("!" if self.invert else "") + dim_str \
                 + DIMENSION_STRING_SEPARATOR_CHAR + range_str

        return string

    def __eq__(self, other: Any) -> bool:
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

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)


class SetCut(Cut):
    """Object describing way of slicing a cube (cell) between two points of a
    dimension that has ordered points. For dimensions with unordered points
    behaviour is unknown."""

    paths: List[HierarchyPath]

    def __init__(self,
            dimension: str,
            paths: List[HierarchyPath],
            hierarchy:str=None,
            invert:bool=False,
            hidden:bool=False) -> None:

        super().__init__(dimension, hierarchy, invert, hidden)
        self.paths = paths

    def to_dict(self) -> JSONType:
        """Returns dictionary representation of the receiver. The keys are:
        `dimension`, `type`=``range`` and `set` as a list of paths."""
        d = super().to_dict()
        d["type"] = "set"
        d["paths"] = self.paths
        return d

    def level_depth(self) -> int:
        """Returns index of deepest level which is equivalent to the longest
        path."""
        return max([len(path) for path in self.paths])

    def __str__(self) -> str:
        """Return string representation of set cut, you can use it in URLs"""
        path_strings = []
        for path in self.paths:
            path_strings.append(string_from_path(path))

        set_string = SET_CUT_SEPARATOR_CHAR.join(path_strings)
        dim_str = string_from_hierarchy(self.dimension, self.hierarchy)
        string = ("!" if self.invert else "") + dim_str \
                 + DIMENSION_STRING_SEPARATOR_CHAR + set_string

        return string

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, SetCut):
            return False
        elif self.dimension != other.dimension:
            return False
        elif self.paths != other.paths:
            return False
        elif self.invert != other.invert:
            return False
        return True

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)


class Cell:
    """Part of a cube determined by slicing dimensions. Immutable object."""

    cuts: List[Cut]

    def __init__(self, cuts: Collection[Cut]=None) -> None:
        self.cuts = list(cuts) if cuts is not None else []

    def __and__(self, other: "Cell") -> "Cell":
        """Returns a new cell that is a conjunction of the two provided
        cells. The cube has to match."""
        cuts = self.cuts + other.cuts
        return Cell(cuts=cuts)

    def to_dict(self) -> JSONType:
        """Returns a dictionary representation of the cell"""

        result = {
            "cuts": [cut.to_dict() for cut in self.cuts]
        }

        return result

    def collect_key_attributes(self, cube: Cube) -> List[Attribute]:
        """Returns an unordered set of key attributes used in the cell's
        cuts."""
        attributes: Set[Attribute] = set()

        dim: Dimension
        hier: Hierarchy

        for cut in self.cuts:
            depth = cut.level_depth()

            if depth == 0:
                continue

            dim = cube.dimension(cut.dimension)
            hier = dim.hierarchy(cut.hierarchy)
            keys = [dim.attribute(level.key.name)
                    for level in hier.levels[0:depth]]
            attributes |= set(keys)

        return list(attributes)

    def slice(self, cut: Cut) -> "Cell":
        """Returns new cell by slicing receiving cell with `cut`. Cut with
        same dimension as `cut` will be replaced, if there is no cut with the
        same dimension, then the `cut` will be appended.
        """

        cuts: List[Cut] = self.cuts[:]
        index = self._dimension_cut_index(cut.dimension)
        if index is not None:
            cuts[index] = cut
        else:
            cuts.append(cut)

        return Cell(cuts=cuts)

    def _dimension_cut_index(self, dimension: str) \
                -> Optional[int]:
        """Returns index of first occurence of cut for `dimension`. Returns
        ``None`` if no cut with `dimension` is found."""
        names = [cut.dimension for cut in self.cuts]

        try:
            index = names.index(dimension)
            return index
        except ValueError:
            return None

    def point_slice(self,
            dimension: str,
            path: HierarchyPath) -> "Cell":
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

        cuts = self.cuts_for_dimension(dimension, exclude=True)
        if path:
            cut = PointCut(dimension, path)
            cuts.append(cut)
        return Cell(cuts=cuts)

    def drilldown(self, dimension: str,
                  value: str,
                  hierarchy: str=None) -> "Cell":
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
        dim_cut = self.point_cut_for_dimension(dimension)

        old_path = dim_cut.path if dim_cut else []
        new_cut = PointCut(dimension, old_path + [value], hierarchy=hierarchy)

        cuts = [cut for cut in self.cuts if cut is not dim_cut]
        cuts.append(new_cut)

        return Cell(cuts=cuts)

    def multi_slice(self, cuts: List[Cut]) -> "Cell":
        """Create another cell by slicing through multiple slices. `cuts` is a
        list of `Cut` object instances. See also :meth:`Cell.slice`."""

        if isinstance(cuts, dict):
            raise CubesError("dict type is not supported any more, use list of Cut instances")

        cell = self
        for cut in cuts:
            cell = cell.slice(cut)

        return cell

    # FIXME: Use dimension_cut_index
    def cut_for_dimension(self, dimension: Dimension) \
            -> Optional[Cut]:
        """Return first found cut for given `dimension`"""

        cut_dimension = None
        for cut in self.cuts:
            cut_dimension = cut.dimension

            if cut_dimension == dimension:
                return cut

        return None

    def point_cut_for_dimension(self, dimension: str) \
            -> Optional[PointCut]:
        """Return first point cut for given `dimension`"""

        cutdim = None
        for cut in self.cuts:
            cutdim = cut.dimension
            if isinstance(cut, PointCut) and cutdim == dimension:
                return cut

        return None

    def level_depths(self) -> Dict[str, int]:
        """Returns a dictionary of dimension names as keys and level depths
        (index of deepest level)."""

        depth: int
        depths: Dict[str,int] = {}

        for cut in self.cuts:
            depth = cut.level_depth()
            dim_name = cut.dimension

            depths[dim_name] = max(depth, depths.get(dim_name, 0))

        return depths

    def cuts_for_dimension(self,
            dimension: str,
            exclude: bool=False) -> List[Cut]:
        """Returns cuts for `dimension`. If `exclude` is `True` then the
        effect is reversed: return all cuts except those with `dimension`."""
        cuts = []
        for cut in self.cuts:
            cut_dimension = cut.dimension
            if (exclude and cut_dimension != dimension) \
                    or (not exclude and cut_dimension == dimension):
                cuts.append(cut)
        return cuts

    def public_cell(self) -> "Cell":
        """Returns a cell that contains only non-hidden cuts. Hidden cuts are
        mostly generated cuts by a backend or an extension. Public cell is a
        cell to be presented to the front-end."""

        cuts = [cut for cut in self.cuts if not cut.hidden]

        return Cell(cuts)

    def __eq__(self, other: Any) -> bool:
        """cells are considered equal if:
            * they refer to the same cube
            * they have same set of cuts (regardless of their order)
        """

        if len(self.cuts) != len(other.cuts):
            return False

        for cut in self.cuts:
            if cut not in other.cuts:
                return False

        return True

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def to_str(self) -> str:
        """Return string representation of the cell by using standard
        cuts-to-string conversion."""
        return string_from_cuts(self.cuts)

    def __str__(self) -> str:
        """Return string representation of the cell by using standard
        cuts-to-string conversion."""
        return string_from_cuts(self.cuts)

    def __repr__(self) -> str:
        return 'Cell(%s)' % (self.to_str() or 'All')

    def __nonzero__(self) -> bool:
        """Returns `True` if the cell contains cuts."""
        return bool(self.cuts)


def cuts_from_string(cube: Cube,
                     string: str,
                     member_converters: Dict[str, MemberConverter]=None,
                     role_member_converters: Dict[str, MemberConverter]=None) \
                             -> List[Cut]:
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



def cut_from_string(string: str,
                    cube:Cube=None,
                    member_converters:Dict[str, MemberConverter]=None,
                    role_member_converters:Dict[str, MemberConverter]=None) \
                            -> Cut:
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

    dimension: Dimension
    hierarchy: Hierarchy
    cut: Cut

    member_converters = member_converters or {}
    role_member_converters = role_member_converters or {}

    dim_hier_pattern = re.compile(r"(?P<invert>!)?"
                                  r"(?P<dim>\w+)(@(?P<hier>\w+))?")

    try:
        (dimspec, string) = DIMENSION_STRING_SEPARATOR.split(string)
    except ValueError:
        raise ArgumentError("Wrong dimension cut string: '%s'" % string)

    match = dim_hier_pattern.match(dimspec)

    if match:
        d = match.groupdict()
        invert = (not not d["invert"])
        dim_name = d["dim"]
        hier_name = d["hier"]
    else:
        raise ArgumentError("Dimension spec '%s' does not match "
                            "pattern 'dimension@hierarchy'" % dimspec)

    converter = member_converters.get(dim_name)
    if cube:
        role = cube.dimension(dim_name).role
        if role is not None:
            converter = converter or role_member_converters.get(role)
            dimension = cube.dimension(dim_name)
            hierarchy = dimension.hierarchy(hier_name)

    # special case: completely empty string means single path element of ''
    # FIXME: why?
    if string == '':
        return PointCut(dim_name, [''], hier_name, invert)

    elif RE_POINT.match(string):
        path = path_from_string(string)

        if converter:
            path = converter(dimension, hierarchy, path)
        cut = PointCut(dim_name, path, hier_name, invert)

    elif RE_SET.match(string):
        paths = list(map(path_from_string, SET_CUT_SEPARATOR.split(string)))

        if converter:
            converted = []
            for path in paths:
                converted.append(converter(dimension, hierarchy, path))
            paths = converted

        cut = SetCut(dim_name, paths, hier_name, invert)

    elif RE_RANGE.match(string):
        (from_path, to_path) = list(map(path_from_string,
                                        RANGE_CUT_SEPARATOR.split(string)))

        if converter:
            from_path = converter(dimension, hierarchy, from_path)
            to_path = converter(dimension, hierarchy, to_path)

        cut = RangeCut(dim_name, from_path, to_path, hier_name, invert)

    else:
        raise ArgumentError("Unknown cut format (check that keys "
                            "consist only of alphanumeric characters and "
                            "underscore): %s" % string)

    return cut

def cut_from_dict(desc: JSONType, cube: Cube=None) -> Cut:
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
PATH_PART_UNESCAPE_PATTERN = re.compile(r"\\([\\!|:;,-])")


def _path_part_escape(path_part: str) -> str:
    if path_part is None:
        return NULL_PATH_VALUE

    return PATH_PART_ESCAPE_PATTERN.sub(r"\\\1", path_part)


def _path_part_unescape(path_part: str) -> Optional[str]:
    if path_part == NULL_PATH_VALUE:
        return None

    return PATH_PART_UNESCAPE_PATTERN.sub(r"\1", path_part)


def string_from_cuts(cuts: Collection[Cut]) -> str:
    """Returns a string represeting `cuts`. String can be used in URLs"""
    strings = [str(cut) for cut in cuts]
    string = CUT_STRING_SEPARATOR_CHAR.join(strings)
    return string


def string_from_path(path: HierarchyPath) -> str:
    """Returns a string representing dimension `path`. If `path` is ``None``
    or empty, then returns empty string. The ptah elements are comma ``,``
    spearated.

    Raises `ValueError` when path elements contain characters that are not
    allowed in path element (alphanumeric and underscore ``_``)."""

    if not path:
        return ""

    path = [_path_part_escape(str(s)) for s in path]

    if not all(map(RE_ELEMENT.match, path)):
        get_logger().warn("Can not convert path to string: "
                          "keys contain invalid characters "
                          "(should be alpha-numeric or underscore) '%s'" %
                          path)

    string = PATH_STRING_SEPARATOR_CHAR.join(path)
    return string


def string_from_hierarchy(dimension: str,
                          hierarchy: Optional[str]) -> str:
    """Returns a string in form ``dimension@hierarchy`` or ``dimension`` if
    `hierarchy` is ``None``"""
    if hierarchy:
        return "{}@{}".format(_path_part_escape(dimension), _path_part_escape(hierarchy))
    else:
        return _path_part_escape(dimension)


def path_from_string(string: str) -> HierarchyPath:
    """Returns a dimension point path from `string`. The path elements are
    separated by comma ``,`` character.

    Returns an empty list when string is empty or ``None``.
    """

    path: HierarchyPath

    if not string:
        return []

    path = PATH_STRING_SEPARATOR.split(string)
    path = [_path_part_unescape(v) for v in path]

    return path


