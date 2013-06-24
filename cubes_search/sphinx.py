"""Multidimensional searching using Sphinx search engine

WARNING: This is just preliminary prototype, use at your own risk of having your application broken
later.

"""
import cubes
import sphinxapi
import xml.sax.saxutils
from xml.sax.xmlreader import AttributesImpl
from sqlalchemy import Table, Column, Integer, String, MetaData, ForeignKey
import sqlalchemy
import collections

EMPTY_ATTRS = AttributesImpl({})

def get_locale_tag(locale, locales):
    try:
        tag = locales.index(locale)
    except ValueError:
        tag = 0

    return tag

class SphinxSearchResult(object):
    def __init__(self, browser):
        super(SphinxSearchResult, self).__init__()
        self.browser = browser
        self.matches = None
        # self.dimension_paths = collections.OrderedDict()
        self.total_found = 0
        self.error = None
        self.warning = None

    # @property
    # def dimensions(self):
    #     return self.dimension_paths.keys()

    def dimension_matches(self, dimension):
        matches = []
        for match in self.matches:
            if match["dimension"] == dimension:
                dup = dict(match)

                path_str = match["path"]
                path = cubes.path_from_string(path_str)
                dup["path"] = path
                dup["path_string"] = path_str
                matches.append(dup)

        return matches

    def values(self, dimension, zipped=False):
        """Return values of search result.

        Attributes:

        * `zipped` - (experimental, might become standard) if ``True`` then
          returns tuples: (`path`, `record`)

        """

        raise NotImplementedError("Fetching values for search matches is not implemented")
        cell = self.browser.full_cube()

        paths = []
        for match in self.matches:
            if match["dimension"] == dimension:
                path_str = match["path"]
                path = cubes.path_from_string(path_str)
                paths.append(path)

        if paths:
            cut = cubes.SetCut(dimension, paths)
            cell.cuts = [cut]
            values = self.browser.values(cell, dimension)
            if zipped:
                # return 0
                return [ {"meta": r[0], "record":r[1]} for r in zip(self.matches, values) ]
            else:
                return values
        else:
            return []


class SphinxSearcher(object):
    """docstring for SphinxSearch"""
    def __init__(self, browser, locales=None, host=None, port=None, **options):
        """Create sphing search object.

        :Parameters:
            * `browser` - Aggregation browser
            * `host` - host where searchd is running (optional)
            * `port` - port where searchd is listening (optional)
        """
        super(SphinxSearcher, self).__init__()
        self.browser = browser
        self.host = host
        self.port = port
        self.options = options
        self.locales = locales or []

    def _dimension_tag(self, dimension):
        """Private method to get integer value from dimension name. Currently it uses
        index in ordered list of dimensions of the browser's cube"""

        names = [dim.name for dim in self.browser.cube.dimensions]
        try:
            tag = names.index(str(dimension))
        except ValueError:
            tag = None
        return tag

    def search(self, query, dimension=None, locale=None):
        """Peform search using Sphinx. If `dimension` is set then only the one dimension will
        be searched."""
        print "SEARCH IN %s QUERY '%s' LOCALE:%s" % (str(dimension), query,
                locale)

        locale_tag = get_locale_tag(locale, self.locales)
        sphinx = sphinxapi.SphinxClient(**self.options)

        if self.host:
            sphinx.SetServer(self.host, self.port)

        if dimension:
            tag = self._dimension_tag(dimension)
            if tag is None:
                raise Exception("No dimension %s" % dimension)

            sphinx.SetFilter("dimension_tag", [tag])

        if locale_tag is not None:
            sphinx.SetFilter("locale_tag", [locale_tag])

        # FIXME: Quick hack for Matej Kurian
        sphinx.SetLimits(0, 1000)

        index_name = self.browser.cube.name

        sphinx.SetSortMode(sphinxapi.SPH_SORT_ATTR_ASC, "attribute_value")
        results = sphinx.Query(query, index = str(index_name))

        result = SphinxSearchResult(self.browser)

        if not results:
            return result

        result.total_found = results["total_found"]

        grouped = collections.OrderedDict()

        result.matches = [match["attrs"] for match in results["matches"]]

        result.error = sphinx.GetLastError()
        result.warning = sphinx.GetLastWarning()

        return result

class XMLSphinxIndexer(object):
    """Create a SQL index for Sphinx"""
    def __init__(self, browser, options=None, out=None):
        """Creates a cube indexer - object that will provide xmlpipe2 data source for Sphinx
        search engine (http://sphinxsearch.com).

        :Attributes:
            * `browser` - configured AggregationBrowser instance

        Generated attributes:
            * id
            * dimension
            * dimension_tag: integer identifying a dimension
            * (hierarchy) - assume default
            * level
            * level key
            * dimension attribute
            * attribute value

        """
        super(XMLSphinxIndexer, self).__init__()

        self.browser = browser
        self.cube = browser.cube
        self.options = options
        self.output = xml.sax.saxutils.XMLGenerator(out=out, encoding = 'utf-8')
        self._counter = 1

    def initialize(self):
        self.output.startDocument()

        self.output.startElement( u'sphinx:docset', EMPTY_ATTRS)

        # START schema
        self.output.startElement( u'sphinx:schema', EMPTY_ATTRS)

        fields = ["value"]

        attributes = [
                      ("locale_tag", "int"),
                      ("dimension", "string"),
                      ("dimension_tag", "int"),
                        ("level", "string"),
                        ("depth", "int"),
                        ("path", "string"),
                        ("attribute", "string"),
                        ("attribute_value", "string"),
                        ("level_key", "string"),
                        ("level_label", "string")]

        for field in fields:
            attrs = AttributesImpl({"name":field})
            self.output.startElement(u'sphinx:field', attrs)
            self.output.endElement(u'sphinx:field')

        for (name, ftype) in attributes:
            attrs = AttributesImpl({"name":name, "type":ftype})
            self.output.startElement(u'sphinx:attr', attrs)
            self.output.endElement(u'sphinx:attr')

        # END schema
        self.output.endElement(u'sphinx:schema')

    def finalize(self):
        self.output.endElement( u'sphinx:docset')
        self.output.endDocument()

    def index(self, locales, **options):
        """Create index records for all dimensions in the cube"""
        # FIXME: this works only for one locale - specified in browser

        # for dimension in self.cube.dimensions:
        self.initialize()
        for locale in locales:
            locale_tag = get_locale_tag(locale, locales)
            for dim_tag, dimension in enumerate(self.cube.dimensions):
                self.index_dimension(dimension, dim_tag,
                                     locale=locale,
                                     locale_tag=
                                     locale_tag,
                                     **options)

        self.finalize()

    def index_dimension(self, dimension, dimension_tag, locale,
                        locale_tag, **options):
        """Create dimension index records."""

        hierarchy = dimension.hierarchy()

        # Switch browser locale
        self.browser.set_locale(locale)
        cell = cubes.Cell(self.cube)

        label_only = bool(options.get("labels_only"))

        for depth_m1, level in enumerate(hierarchy.levels):
            depth = depth_m1 + 1

            levels = hierarchy.levels[0:depth]
            keys = [level.key.ref() for level in levels]
            level_key = keys[-1]
            level_label = (level.label_attribute.ref())

            for record in self.browser.values(cell, dimension, depth):
                path = [record[key] for key in keys]
                path_string = cubes.string_from_path(path)

                for attr in level.attributes:
                    if label_only and str(attr) != str(level.label_attribute):
                        continue

                    fname = attr.ref()
                    irecord = {
                        "locale_tag": locale_tag,
                        "dimension": dimension.name,
                        "dimension_tag": dimension_tag,
                        "level": level.name,
                        "depth": depth,
                        "path": path_string,
                        "attribute": attr.name,
                        "value": record[fname],
                        "level_key": record[level_key],
                        "level_label": record[level_label]
                        }

                    self.add(irecord)
    def add(self, irecord):
        """Emits index record (sphinx document) to the output XML stream."""

        attrs = AttributesImpl({"id":str(self._counter)})
        self._counter += 1

        self.output.startElement( u'sphinx:document', attrs)

        record = dict(irecord)
        record["attribute_value"] = record["value"]

        attrs = AttributesImpl({})
        for key, value in record.items():
            self.output.startElement( key, attrs)
            self.output.characters(unicode(value))
            self.output.endElement(key)

        self.output.endElement( u'sphinx:document')

