import logging
import json
import decimal
import copy
import re
from collections import namedtuple

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from cubes.errors import *
from .model import Dimension, Cube
from .common import get_logger

__all__ = [
    "AggregationBrowser",
    "Cell",
    "Cut",
    "PointCut",
    "RangeCut",
    "SetCut",
    "AggregationResult",
    "cuts_from_string",
    "string_from_cuts",
    "string_from_path",
    "path_from_string",
    "cut_from_string",
    "cut_from_dict",
    "DrilldownRow",
    "CrossTable",
    "cross_table"
]

class AggregationBrowser(object):
    """Class for browsing data cube aggregations

    :Attributes:
      * `cube` - cube for browsing

    """

    features = []
    """List of browser features as strings."""

    def __init__(self, cube):
        super(AggregationBrowser, self).__init__()

        if not cube:
            raise ArgumentError("No cube given for aggregation browser")

        self.cube = cube

    def full_cube(self):
        return Cell(self.cube)

    def dimension_object(self, dimension):
        """Helper function to return proper dimension object as a subclass of
        Dimension.

        .. Warning::

            Depreciated. Use :meth:`cubes.Cube.dimension`

        Arguments:

        * `dimension` - a dimension object or a string, if it is a string,
          then dimension object is retrieved from cube
        """
        # FIXME: depreciate, use cube.dimension(...) directly

        if type(dimension) == str:
            return self.cube.dimension(dimension)
        else:
            return dimension

    def aggregate(self, cell=None, measures=None, drilldown=None, **options):
        """Return aggregate of a cell.

        Subclasses of aggregation browser should implement this method.

        :Attributes:

        * `drilldown` - dimensions and levels through which to drill-down,
          default `None`
        * `measures` - list of measures to be aggregated. By default all
          measures are aggregated.

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

        Retruns a :class:AggregationResult object.
        """
        raise NotImplementedError

    def facts(self, cell=None, **options):
        """Return an iterable object with of all facts within cell"""

        raise NotImplementedError

    def fact(self, key):
        """Returns a single fact from cube specified by fact key `key`"""
        raise NotImplementedError

    def values(self, cell, dimension, depth=None, paths=None, 
               hierarchy=None, **options):
        """Return values for `dimension` with level depth `depth`. If `depth`
        is ``None``, all levels are returned.

        .. note::

            Some backends might support only default hierarchy. 
        """
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
                raise ArgumentError("Unknown report query '%s' for '%s'" % (query_type, result_name))

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

        # TODO: is the name right?
        # TODO: dictionary or class representation?
        # TODO: how we can add the cell as well?
        if not cell:
            return []

        if dimension:
            cuts = [cut for cut in cell.cuts if str(cut.dimension)==str(dimension)]
        else:
            cuts = cell.cuts

        details = [self.cut_details(cut) for cut in cuts]

        return details

    def cut_details(self, cut):
        """Returns details for a `cut` which should be a `Cut` instance.

        * `PointCut` - all attributes for each level in the path
        * `SetCut` - list of `PointCut` results, one per path in the set
        * `RangeCut` - `PointCut`-like results for lower range (from) and
          upper range (to)

        Default implemenatation uses `AggregationBrowser.values()` for each
        path. Backends might customize this method to make it more efficient.

        """

        dimension = self.cube.dimension(cut.dimension)

        if isinstance(cut, PointCut):
            details = self._path_details(dimension, cut.path)

        elif isinstance(cut, SetCut):
            details = [self._path_details(dimension, path) for path in cut.paths]

        elif isinstance(cut, RangeCut):
            details = {
                "from": self._path_details(dimension, cut.from_path),
                "to": self._path_details(dimension, cut.to_path)
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

        cut = PointCut(dimension, path)
        cell = Cell(self.cube, cuts=[cut])
        dim_values = list(self.values(cell, dimension, len(path)))

        if len(dim_values) > 1:
            raise Exception("There are more than one detail rows for dimension %s path %s" % \
                                (str(dimension), path) )

        if not dim_values:
            return None

        details = dim_values[0]

        if (dimension.is_flat and not dimension.has_details):
            name = dimension.all_attributes()[0].name
            value = details.get(name)
            item = { name: value }
            item["_key"] = value
            item["_label"] = value
            result = [item]
        else:
            result = []
            for level in hierarchy.levels_for_path(path):
                item = {a.ref():details.get(a.ref()) for a in level.attributes}
                item["_key"] = details.get(level.key.ref())
                item["_label"] = details.get(level.label_attribute.ref())
                result.append(item)

        return result

class Cell(object):
    """Part of a cube determined by slicing dimensions. Immutable object."""
    def __init__(self, cube=None, cuts=[]):
        if not isinstance(cube, Cube):
            raise ArgumentError("Cell cube should be sublcass of Cube, "
                                          "provided: %s" % type(cube).__name__)
        self.cube = cube
        self.cuts = cuts

    def to_dict(self):
        """Returns a dictionary representation of the cell"""
        result = {
            "cube": str(self.cube.name),
            "cuts": [cut.to_dict() for cut in self.cuts]
        }

        return result;

    def slice(self, cut, dummy=None):
        """Returns new cell by slicing receiving cell with `cut`. Cut with
        same dimension as `cut` will be replaced, if there is no cut with the
        same dimension, then the `cut` will be appended.
        """

        # Fix for wrong early design decision:
        if isinstance(cut, Dimension) or isinstance(cut, basestring):
            raise CubesError("slice() should now be called with a cut (since v0.9.2). To get "
                             "original behaviour of one-dimension point cut, "
                             "use point_slice(dim, path) instead or better: "
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
        cuts = self._filter_dimension_cuts(dimension, exclude=True)
        if path:
            cut = PointCut(dimension, path)
            cuts.append(cut)
        return Cell(cube=self.cube, cuts=cuts)

    def drilldown(self, dimension, value):
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

        Returns: new derived cell object.
        """
        dimension = self.cube.dimension(dimension)
        dim_cut = self.cut_for_dimension(dimension)

        old_path = dim_cut.path if dim_cut else []
        new_cut = PointCut(dimension, old_path + [value])

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

        Returns new cell object.

        .. note::

                Only default hierarchy is currently supported.
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
            new_cut = PointCut(dimension, rollup_path)
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
        if isinstance(rollup, basestring):
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

        # TODO: should accept hierarchies

        levels = {}

        for cut in self.cuts:
            level = cut.level_depth()
            dim = self.cube.dimension(cut.dimension)
            dim_name = str(dim)

            levels[dim_name] = max(level, levels.get(dim_name))

        return levels

    def is_base(self, dimension, hierarchy=None):
        """Returns ``True`` when cell is base cell for `dimension`. Cell
        is base if there is a point cut with path referring to the
        most detailed level of the dimension `hierarchy`."""


        hierarchy = dimension.hierarchy(hierarchy)

        dim_cut = None
        for cut in self.cuts:
            if isinstance(cut, PointCut) and cut.dimension == dimension:
                dim_cut = cut
                break

        depth = dim_cut.level_depth() if dim_cut else None

        return depth == len(hierarchy)

    # def level(self, ):

    def _filter_dimension_cuts(self, dimension, exclude=False):
        dimension = self.cube.dimension(dimension)
        cuts = []
        for cut in self.cuts:
            if (exclude and cut.dimension != dimension) \
                    or (not exclude and cut.dimension == dimension):
                cuts.append(cut)
        return cuts

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
        return self.to_str()

CUT_STRING_SEPARATOR = '|'
DIMENSION_STRING_SEPARATOR = ':'
PATH_STRING_SEPARATOR = ','
RANGE_CUT_SEPARATOR = '-'
SET_CUT_SEPARATOR = '+'

"""
point: date:2004
range: date:2004-2010
set ?1 : date:2004+2010+2011,04+
set ?2 : date:[2004;2010;2033,04]

"""

def cuts_from_string(string):
    """Return list of cuts specified in `string`. You can use this function to
    parse cuts encoded in a URL.
    
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

    Sets are in form ``path1+path2+path3`` (none of the paths should be
    empty)::

        date:2004+2010
        date:2004+2005,1+2010,10

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

    dim_cuts = string.split(CUT_STRING_SEPARATOR)
    for dim_cut in dim_cuts:
        (dimension, cut_string) = dim_cut.split(DIMENSION_STRING_SEPARATOR)
        cuts.append(cut_from_string(dimension, cut_string))

    return cuts

re_element = re.compile(r"^[\w,]*$")
re_point = re.compile(r"^[\w,]*$")
re_set = re.compile(r"^([\w,]+)(\+([\w,]+))+$")
re_range = re.compile(r"^([\w,]*)-([\w,]*)$")

def cut_from_string(dimension, string):
    """Returns a cut from `string` with dimension `dimension. The string
    should match one of the following patterns:
    
    * point cut: ``2010,2,4``
    * range cut: ``2010-2012``, ``2010,1-2012,3,5``, ``2010,1-`` (open range)
    * set cut: ``2010+2012``, ``2010,1+2012,3,5+2012,10``
    
    If the `string` does not match any of the patterns, then exception is
    raised.
    """
    if re_point.match(string):
        return PointCut(dimension, path_from_string(string))
    elif re_set.match(string):
        paths = map(path_from_string, string.split(SET_CUT_SEPARATOR))
        return SetCut(dimension, paths)
    elif re_range.match(string):
        (from_path, to_path) = map(path_from_string, string.split(RANGE_CUT_SEPARATOR))
        return RangeCut(dimension, from_path, to_path)
    else:
        raise Exception("Unknown cut format (check that keys "
                        "consist only of of alphanumeric characters and "
                        "underscore)")
                        
def cut_from_dict(desc, cube=None):
    """Returns a cut from `desc` dictionary. If `cube` is specified, then the
    dimension is looked up in the cube and set as `Dimension` instances, if
    specified as strings."""

    cut_type = desc["type"].lower()

    dim = desc.get("dimension")

    if dim and cube:
        dim = cube.dimension(dim)
        
    if cut_type == "point":
        return PointCut(dim, desc.get("path"))
    elif cut_type == "set":
        return SetCut(dim, desc.get("paths"))
    elif cut_type == "range":
        return RangeCut(dim, desc.get("from"), desc.get("to"))
    else:
        raise ArgumentError("Unknown cut type %s" % cut_type)

def string_from_cuts(cuts):
    """Returns a string represeting `cuts`. String can be used in URLs"""
    strings = [str(cut) for cut in cuts]
    string = CUT_STRING_SEPARATOR.join(strings)
    return string

def string_from_path(path):
    """Returns a string representing dimension `path`. If `path` is ``None``
    or empty, then returns empty string. The ptah elements are comma ``,``
    spearated.

    Raises `ValueError` when path elements contain characters that are not
    allowed in path element (alphanumeric and underscore ``_``)."""

    if not path:
        return ""

    # FIXME: do some escaping or something like URL encoding
    path = [unicode(s) if s is not None else "" for s in path]

    if not all(map(re_element.match, path)):
        raise ArgumentError("Can not convert path to string: "
                            "keys contain invalid characters "
                            "(should be alpha-numeric or underscore)")

    string = PATH_STRING_SEPARATOR.join(path)
    return string

def path_from_string(string):
    """Returns a dimension point path from `string`. The path elements are
    separated by comma ``,`` character.

    Returns an empty list when string is empty or ``None``.
    """

    if not string:
        return []

    path = string.split(PATH_STRING_SEPARATOR)
    path = [v if v != "" else None for v in path]

    return path

class Cut(object):
    def __init__(self, dimension):
        self.dimension = dimension

    def to_dict(self):
        """Returns dictionary representation fo the receiver. The keys are:
        `dimension`."""
        d = {
            "dimension": str(self.dimension),
            "level_depth": self.level_depth()
        }
        return d

    def level_depth(self):
        """Returns deepest level number. Subclasses should implement this
        method"""
        raise NotImplementedError

class PointCut(Cut):
    """Object describing way of slicing a cube (cell) through point in a
    dimension"""

    def __init__(self, dimension, path):
        super(PointCut, self).__init__(dimension)
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

        if type(self.dimension) == str or type(self.dimension) == unicode:
            dim_name = self.dimension
        else:
            dim_name = self.dimension.name

        string = dim_name + DIMENSION_STRING_SEPARATOR + path_str

        return string

    def __repr__(self):
        if isinstance(self.dimension, basestring):
            dim_name = self.dimension
        else:
            dim_name = self.dimension.name

        return '{"cut": "%s", "dimension":"%s", "path": "%s"}' % ("PointCut", dim_name, self.path)

    def __eq__(self, other):
        if self.dimension != other.dimension:
            return False
        elif self.path != other.path:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

class RangeCut(Cut):
    """Object describing way of slicing a cube (cell) between two points of a
    dimension that has ordered points. For dimensions with unordered points
    behaviour is unknown."""

    def __init__(self, dimension, from_path, to_path):
        super(RangeCut, self).__init__(dimension)
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

        if type(self.dimension) == str or type(self.dimension) == unicode:
            dim_name = self.dimension
        else:
            dim_name = self.dimension.name

        range_str = from_path_str + RANGE_CUT_SEPARATOR + to_path_str
        string = dim_name + DIMENSION_STRING_SEPARATOR + range_str

        return string

    def __repr__(self):
        if type(self.dimension) == str:
            dim_name = self.dimension
        else:
            dim_name = self.dimension.name

        return '{"cut": "%s", "dimension":"%s", "from": "%s", "to": "%s"}' % \
                    ("RangeCut", dim_name, self.from_path, self.to_path)

    def __eq__(self, other):
        if self.dimension != other.dimension:
            return False
        elif self.from_path != other.from_path:
            return False
        elif self.to_path != other.to_path:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

class SetCut(Cut):
    """Object describing way of slicing a cube (cell) between two points of a
    dimension that has ordered points. For dimensions with unordered points
    behaviour is unknown."""

    def __init__(self, dimension, paths):
        super(SetCut, self).__init__(dimension)
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

        if type(self.dimension) == str or type(self.dimension) == unicode:
            dim_name = self.dimension
        else:
            dim_name = self.dimension.name

        set_string = SET_CUT_SEPARATOR.join(path_strings)
        string = dim_name + DIMENSION_STRING_SEPARATOR + set_string

        return string

    def __repr__(self):
        if type(self.dimension) == str:
            dim_name = self.dimension
        else:
            dim_name = self.dimension.name

        return '{"cut": "%s", "dimension":"%s", "paths": "%s"}' % \
                    ("SetCut", dim_name, self.paths)

    def __eq__(self, other):
        if self.dimension != other.dimension:
            return False
        elif self.paths != other.paths:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

DrilldownRow = namedtuple("DrilldownRow", ["key", "label", "path", "record"])

class AggregationResult(object):
    """Result of aggregation or drill down.

    Attributes:

    * `summary` - dictionary of summary row fields
    * `cells` - list of cells that were drilled-down
    * `remainder` - summary of remaining cells (not yet implemented)
    * `total_cell_count` - number of total cells in drill-down (after limit,
      before pagination)

    """
    def __init__(self):
        super(AggregationResult, self).__init__()
        self.summary = {}
        self.cells = []
        self.remainder = {}
        self.total_cell_count = None
        self.cell = None

    @property
    def drilldown(self):
        logger = get_logger()
        logger.warn("AggregationResult.drilldown is depreciated, use '.cells' instead")
        return self.cells

    @drilldown.setter
    def drilldown(self, val):
        logger = get_logger()
        logger.warn("AggregationResult.drilldown is depreciated, use '.cells' instead")
        self.cells = val

    def to_dict(self):
        """Return dictionary representation of the aggregation result. Can be
        used for JSON serialisation."""

        d = {}

        d["summary"] = self.summary
        d["remainder"] = self.remainder
        d["cells"] = self.cells
        d["total_cell_count"] = self.total_cell_count

        if self.cell:
            d["cell"] = [cut.to_dict() for cut in self.cell.cuts]
        else:
            d["cell"] = None

        return d

    def as_json(self):
        # FIXME: Eiter depreciate this or move it into backend. Also provide
        # option for iterable result

        def default(o):
            if type(o) == decimal.Decimal:
                return float(o)
            else:
                return JSONEncoder.default(self, o)

        encoder = json.JSONEncoder(default = default, indent = 4)
        json_string = encoder.encode(self.as_dict())

        return json_string

    def table_rows(self, dimension, depth=None):
        """Returns iterator of drilled-down rows which yields a named tuple with
        named attributes: (key, label, path, record). `depth` is last level of
        interest. If not specified (set to ``None``) then deepest level for
        `dimension` is used.

        * `key`: value of key dimension attribute at level of interest
        * `label`: value of label dimension attribute at level of interest
        * `path`: full path for the drilled-down cell
        * `record`: all drill-down attributes of the cell

        Example use::

            for row in result.table_rows(dimension):
                print "%s: %s" % (row.label, row.record["record_count"])

        `dimension` has to be :class:`cubes.Dimension` object. Raises
        `TypeError` when cut for `dimension` is not `PointCut`.
        """

        cut = self.cell.cut_for_dimension(dimension)

        if cut and not isinstance(cut, PointCut):
            raise TypeError("PointCut expected for drill down iterator dimension '%s' cut (was %s)" % (dimension, type(cut)))

        path = cut.path if cut else []

        # FIXME: use hierarchy from cut (when implemented)
        dimension = self.cell.cube.dimension(dimension)
        hierarchy = dimension.hierarchy()

        if depth:
            current_level = hierarchy[depth-1]
        else:
            levels = hierarchy.levels_for_path(path, drilldown=True)
            current_level = levels[-1]

        level_key = current_level.key.full_name()
        level_label = current_level.label_attribute.ref()

        for record in self.cells:
            drill_path = path[:] + [record[level_key]]

            row = DrilldownRow(record[level_key],
                               record[level_label],
                               drill_path,
                               record)
            yield row

    def cross_table(self, onrows, oncolumns, measures=None):
        """
        Creates a cross table from result's drilldown. `onrows`
        contains list of attribute names to be placed at rows and `oncolumns`
        contains list of attribute names to be placet at columns. `measures` is a
        list of measures to be put into cells. If measures are not specified, then
        only ``record_count`` is used.

        Returns a named tuble with attributes:

        * `columns` - labels of columns. The tuples correspond to values of
          attributes in `oncolumns`.
        * `rows` - labels of rows as list of tuples. The tuples correspond to
          values of attributes in `onrows`.
        * `data` - list of measure data per row. Each row is a list of measure
          tuples as specified in `measures`.

        .. warning::

            Experimental implementation. Interface might change - either
            arguments or result object.

        """

        return cross_table(self.drilldown, onrows, oncolumns, measures)

CrossTable = namedtuple("CrossTable", ["columns", "rows", "data"])

def cross_table(drilldown, onrows, oncolumns, measures=None):
    """
    Creates a cross table from a drilldown (might be any list of records).
    `onrows` contains list of attribute names to be placed at rows and
    `oncolumns` contains list of attribute names to be placet at columns.
    `measures` is a list of measures to be put into cells. If measures are not
    specified, then only ``record_count`` is used.

    Returns a named tuble with attributes:

    * `columns` - labels of columns. The tuples correspond to values of
      attributes in `oncolumns`.
    * `rows` - labels of rows as list of tuples. The tuples correspond to
      values of attributes in `onrows`.
    * `data` - list of measure data per row. Each row is a list of measure
      tuples.

    .. warning::

        Experimental implementation. Interface might change - either
        arguments or result object.

    """

    matrix = {}
    row_hdrs = []
    column_hdrs = []

    measures = measures or ["record_count"]

    for record in drilldown:
        hrow = tuple(record[f] for f in onrows)
        hcol = tuple(record[f] for f in oncolumns)

        if not hrow in row_hdrs:
            row_hdrs.append(hrow)
        if not hcol in column_hdrs:
            column_hdrs.append(hcol)

        matrix[(hrow, hcol)] = tuple(record[m] for m in measures)

    data = []
    for hrow in row_hdrs:
        row = [matrix.get((hrow, hcol)) for hcol in column_hdrs]
        data.append(row)

    return CrossTable(column_hdrs, row_hdrs, data)
