import logging
import json
import decimal
import copy

def default_logger_name():
    return 'brewery.cubes'


class AggregationBrowser(object):
    """Class for browsing data cube aggregations

    :Attributes:
    * `cube` - cube for browsing
    """

    def __init__(self, cube):
        super(AggregationBrowser, self).__init__()

        if not cube:
            raise AttributeError("No cube given for aggregation browser")

        self.cube = cube

    def full_cube(self):
        return Cuboid(self)

    def dimension_object(self, dimension):
        """Helper function to return proper dimension object as a subclass of Dimension.

        .. Warning::
        
            Depreciated. Use :meth:`cubes.Cube.dimension`

        :Arguments:
            * `dimension` - a dimension object or a string, if it is a string, then dimension object
                is retrieved from cube
        """

        if type(dimension) == str:
            return self.cube.dimension(dimension)
        else:
            return dimension

    def aggregate(self, cuboid, measures = None, drilldown = None, **options):
        """Return aggregate of a cuboid.

        Subclasses of aggregation browser should implement this method.

        :Attributes:

            * `drilldown` - dimensions and levels through which to drill-down, default `None`
            * `measures` - list of measures to be aggregated. By default all measures are
              aggregated.
            
        Drill down can be specified in two ways: as a list of dimensions or as a dictionary. If it
        is specified as list of dimensions, then cuboid is going to be drilled down on the next
        level of specified dimension. Say you have a cuboid for year 2010 and you want to drill
        down by months, then you specify ``drilldown = ["date"]``.
        
        If `drilldown` is a dictionary, then key is dimension or dimension name and value is last
        level to be drilled-down by. If the cuboid is at `year` level and drill down is: ``{
        "date": "day" }`` then both `month` and `day` levels are added.
        
        If there are no more levels to be drilled down, an exception is raised. Say your model has
        three levels of the `date` dimension: `year`, `month`, `day` and you try to drill down by
        `date` then ``ValueError`` will be raised.
        
        Retruns a :class:AggregationResult object.
        """
        raise NotImplementedError
        
    def facts(self, cuboid, **options):
        """Return list of all facts within cuboid"""
        
        raise NotImplementedError

    def fact(self, key):
        """Returns a single fact from cube specified by fact key `key`"""
        raise NotImplementedError

    def values(self, cuboid, dimension, depth = None, **options):
        """Return values for `dimension` with level depth `depth`. If `depth` is ``None``, all
        levels are returned.
        
        .. note::
            
            Currently only default hierarchy is used. 
        """
        
class Cuboid(object):
    """Part of a cube determined by slicing dimensions. Immutable object."""
    def __init__(self, browser, cuts = []):
        self.browser = browser
        self.cube = browser.cube
        self.cuts = cuts

    def slice(self, dimension, path):
        """Create another cuboid by slicing receiving cuboid through `dimension` at `path`.
        Receiving object is not modified. If cut with dimension exists it is replaced with new one.
        If path is empty list or is none, then cut for given dimension is removed.

        Example::

            full_cube = browser.full_cube()
            contracts_2010 = full_cube.slice("date", [2010])

        Returns: new derived Cuboid object.
        """
        dimension = self.browser.dimension_object(dimension)
        cuts = self._filter_dimension_cuts(dimension, exclude = True)
        if path:
            cut = PointCut(dimension, path)
            cuts.append(cut)
        return Cuboid(self.browser, cuts = cuts)

    def multi_slice(self, cuts):
        """Create another cuboid by slicing through multiple slices. `cuts` can be list or a dictionry.
        If it is a list, it should be a list of two item tuples where first item is a dimension, second
        item is a dimension cut path. If `cuts` is a dictionary, then keys are dimensions, values are
        cut paths.

        See :meth:`Cuboid.slice` for more information about slicing."""

        cuboid = self

        if type(cuts) == dict:
            for dim, path in cuts.items():
                cuboid = cuboid.slice(dim, path)
        elif type(cuts) == list or type(cuts) == tuple:
            for dim, path in cuts:
                cuboid = cuboid.slice(dim, path)
        else:
            raise TypeError("Cuts for multi_slice sohuld be a list or a dictionary, is '%s'" \
                                % cuts.__class__)

        return cuboid

    def cut_for_dimension(self, dimension):
        """Return first found cut for given `dimension`"""
        dimension = self.browser.cube.dimension(dimension)

        cut_dimension = None
        for cut in self.cuts:
            try:
                cut_dimension = self.browser.cube.dimension(cut.dimension)
            except:
                pass

            if cut_dimension == dimension:
                return cut

        return None

    def _filter_dimension_cuts(self, dimension, exclude = False):
        dimension = self.browser.cube.dimension(dimension)
        cuts = []
        for cut in self.cuts:
            if (exclude and cut.dimension != dimension) or (not exclude and cut.dimension == dimension):
                cuts.append(cut)
        return cuts

    def aggregate(self, measures = None, drilldown = None, **options):
        """Return computed aggregate of the coboid.
        """

        return self.browser.aggregate(self, measures, drilldown, **options)

    def values(self, dimension, depth = None, **options):
        """Return values for dimension."""
        return self.browser.values(self, dimension, depth, **options)

    def facts(self, **options):
        """Get all facts within cuboid."""
        return self.browser.facts(self, **options)

    def __eq__(self, other):
        """Cuboids are considered equal if:
            * they refer to the same cube within same browser
            * they have same set of cuts (regardless of their order)
        """

        if self.browser != other.browser:
            return False
        elif self.cube != other.cube:
            return False

        if len(self.cuts) != len(other.cuts):
            return False

        for cut in self.cuts:
            if cut not in other.cuts:
                return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

CUT_STRING_SEPARATOR = '|'
DIMENSION_STRING_SEPARATOR = ':'
PATH_STRING_SEPARATOR = ','

def cuts_from_string(string):
    """Return list of cuts specified in `string`. You can use this function to parse cuts encoded
    in a URL.
    
    Grammar::
    
        <list> ::= <cut> | <cut> '|' <list>
        <cut> ::= <dimension> ':' <path>
        <dimension> ::= <identifier>
        <path> ::= <value> | <value> ',' <path>
        
    Examples::

        date:2004
        date:2004,1
        date:2004,1|class=5
        date:2004,1,1|category:5,10,12|class:5

    The characters '|', ':' and ',' are configured in `CUT_STRING_SEPARATOR`,
    `DIMENSION_STRING_SEPARATOR`, `PATH_STRING_SEPARATOR` respectively.
    """
    cut_strings = string.split(CUT_STRING_SEPARATOR)

    if not cut_strings:
        return []

    cuts = []
    
    for cut_string in cut_strings:
        (dimension_name, path_string) = cut_string.split(DIMENSION_STRING_SEPARATOR)
        
        path = path_string.split(PATH_STRING_SEPARATOR)
        if not path:
            path = []
        cut = PointCut(dimension_name, path)
        cuts.append(cut)
        
    return cuts

def string_from_cuts(cuts):
    """Returns a string represeting cuts. String can be used in URLs"""
    strings = [str(cut) for cut in cuts]
    string = CUT_STRING_SEPARATOR.join(strings)
    return string

class PointCut(object):
    """Object describing way of slicing a cube (cuboid) through point in a dimension"""

    def __init__(self, dimension, path):
        self.dimension = dimension
        self.path = path

    def __str__(self):
        """Return string representation of point cut, you can use it in URLs"""
        strings = [str(value) for value in self.path]
        path_str = PATH_STRING_SEPARATOR.join(strings)
        
        if type(self.dimension) == str or type(self.dimension) == unicode:
            dim_name = self.dimension
        else:
            dim_name = self.dimension.name
            
        string = dim_name + DIMENSION_STRING_SEPARATOR + path_str
        
        return string        

    def __repr__(self):
        if type(self.dimension) == str:
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


class AggregationResult(object):
    """docstring for AggregationResult"""
    def __init__(self):
        super(AggregationResult, self).__init__()
        self.summary = {}
        self.drilldown = {}
        self.remainder = {}

    def as_dict(self):
        d = {}
        
        d["summary"] = self.summary
        d["drilldown"] = self.drilldown
        d["remainder"] = self.remainder
        
        return d

    def as_json(self):
        def default(o):
            if type(o) == decimal.Decimal:
                return float(o)
            else:
                return JSONEncoder.default(self, o)

        encoder = json.JSONEncoder(default = default, indent = 4)
        json_string = encoder.encode(self.as_dict())

        return json_string
