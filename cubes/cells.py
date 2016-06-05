# -*- coding: utf-8 -*-

from __future__ import absolute_import

import copy
import re

from collections import OrderedDict

from .errors import ArgumentError, CubesError
from .model import Dimension, Cube
from .logging import get_logger
from . import compat


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
                                % (self.cube.name, other.cube.name))
        cuts = self.cuts + other.cuts
        return Cell(self.cube, cuts=cuts)

    def to_dict(self):
        """Returns a dictionary representation of the cell"""
        result = {
            "cube": str(self.cube.name),
            "cuts": [cut.to_dict() for cut in self.cuts]
        }

        return result

    @property
    def all_attributes(self):
        """Returns an unordered set of key attributes used in the cell's
        cuts."""
        attributes = set()

        for cut in self.cuts:
            depth = cut.level_depth()
            if depth:
                dim = self.cube.dimension(cut.dimension)
                hier = dim.hierarchy(cut.hierarchy)
                keys = [dim.attribute(level.key.name) for level in hier[0:depth]]
                attributes |= set(keys)

        return list(attributes)

    # Backward compatibility
    # TODO: issue warning
    @property
    def key_attributes(self):
        return self.all_attributes


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

        if isinstance(rollup, (list, tuple)):
            for dim_name in rollup:
                cut = cuts.get(dim_name)
                if cut is None:
                    continue
                #     raise ValueError("No cut to roll-up for dimension '%s'" % dim_name)
                if isinstance(cut, PointCut):
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

                dim = self.cube.dimension(cut.dimension)
                hier = dim.default_hierarchy

                rollup_path = hier.rollup(cut.path, level_name)

                cut = PointCut(cut.dimension, rollup_path)
                new_cuts.append(cut)
        else:
            raise ArgumentError("Rollup is of unknown type: %s" %
                                type(self.drilldown))

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
PATH_PART_UNESCAPE_PATTERN = re.compile(r"\\([\\!|:;,-])")


def _path_part_escape(path_part):
    if path_part is None:
        return NULL_PATH_VALUE

    return PATH_PART_ESCAPE_PATTERN.sub(r"\\\1", compat.to_unicode(path_part))


def _path_part_unescape(path_part):
    if path_part == NULL_PATH_VALUE:
        return None

    return PATH_PART_UNESCAPE_PATTERN.sub(r"\1", compat.to_unicode(path_part))


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
        string = ("!" if self.invert else "") + dim_str \
                 + DIMENSION_STRING_SEPARATOR_CHAR + range_str

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
        string = ("!" if self.invert else "") + dim_str \
                 + DIMENSION_STRING_SEPARATOR_CHAR + set_string

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

