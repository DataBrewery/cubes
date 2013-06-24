import os
import shutil
import cubes
from cubes.common import to_unicode_string

try:
    from whoosh import index
    from whoosh.fields import Schema, TEXT, KEYWORD, ID, STORED, NUMERIC
    from whoosh.qparser import QueryParser
    from whoosh.query import Term
    from whoosh.sorting import FieldFacet

except ImportError:
    from cubes.common import MissingPackage
    m = MissingPackage('whoosh', "search engine backend")
    Schema = index = m

class WhooshIndexer(object):
    """Create a SQL index for Sphinx"""
    def __init__(self, browser, config=None):
        """Creates a cube indexer - object that will provide xmlpipe2 data source for Sphinx
        search engine (http://sphinxsearch.com).

        :Attributes:
            * `browser` - configured AggregationBrowser instance

        Generated attributes:
            * id
            * dimension
            * (hierarchy) - assume default
            * level
            * level key
            * dimension attribute
            * attribute value

        Config has to have section `search` with option `index_path` which is
        root path to indexes - one subdirectory per cube.

        """
        super(WhooshIndexer, self).__init__()

        self.root_path = config.get("search", "index_path")
        self.browser = browser
        self.cube = browser.cube
        self.path = os.path.join(self.root_path, str(self.cube))
        self.logger = self.browser.logger

        # FIXME: this is redundant, make one index per dimension or something
        # FIXME: the above requirement needs cubes browser to provide list of
        # all dimension values, which is not currently implemented nor in the
        # API definition

    def index(self, locales, init=False, **options):
        """Create index records for all dimensions in the cube"""
        # FIXME: this works only for one locale - specified in browser

        if init:
            self.initialize()

        if not index.exists_in(self.path):
            raise Exception("Index is not initialized in '%s'" % self.path)

        ix = index.open_dir(self.path)

        self.writer = ix.writer()
        # for dimension in self.cube.dimensions:
        options = options or {}
        cube = self.browser.cube

        for locale_tag, locale in enumerate(locales):
            for dim_tag, dimension in enumerate(cube.dimensions):
                self.index_dimension(dimension, dim_tag,
                                     locale=locale,
                                     locale_tag=locale_tag,
                                     **options)
        self.writer.commit()

    def index_dimension(self, dimension, dimension_tag, locale,
                        locale_tag, **options):
        """Create dimension index records.

        If `Attribute.info` has key `no_search` set to `True`, then the field
        is skipped
        """

        print "indexing %s, locale: %s" % (dimension, locale)

        hierarchy = dimension.hierarchy()

        # Switch browser locale
        self.browser.set_locale(locale)
        cell = cubes.Cell(self.cube)

        for depth_m1, level in enumerate(hierarchy.levels):
            depth = depth_m1 + 1

            levels = hierarchy.levels[0:depth]
            keys = [level.key.ref() for level in levels]
            level_key = keys[-1]
            level_label = (level.label_attribute.ref())

            if options.get("labels_only"):
                attributes = [level.label_attribute]
            else:
                attributes = []
                for attr in level.attributes:
                    if not attr.info or \
                            (attr.info and not attr.info.get("no_search")):
                        attributes.append(attr)

            for record in self.browser.values(cell, dimension, depth):
                print "Dimension value: %s" % record
                path = [record[key] for key in keys]
                path_string = cubes.string_from_path(path)

                for attr in attributes:
                    ref = to_unicode_string(attr.ref())
                    self.writer.add_document(
                        locale=to_unicode_string(locale),
                        dimension=dimension.name,
                        level=level.name,
                        depth=depth,
                        path=path_string,
                        level_key=record[level_key],
                        level_label=record[level_label],
                        attribute=attr.name,
                        value=to_unicode_string(record[ref])
                    )

    def initialize(self):
        if index.exists_in(self.path):
            self.logger.info("removing old index at '%s'" % self.path)
            shutil.rmtree(self.path)

        if not os.path.exists(self.path):
            self.logger.info("creating index at '%s'" % self.path)
            os.mkdir(self.path)

        schema = Schema(
                    locale=TEXT(stored=True),
                    dimension=TEXT(stored=True),
                    level=STORED,
                    depth=STORED,
                    path=STORED,
                    level_key=STORED,
                    level_label=STORED,
                    attribute=STORED,
                    value=TEXT(stored=True)
                )

        ix = index.create_in(self.path, schema)


class WhooshSearcher(object):
    def __init__(self, browser, locales=None, index_path=None,
                    default_limit=None, **options):

        super(WhooshSearcher, self).__init__()
        self.browser = browser
        self.cube = self.browser.cube

        self.root_path = index_path
        self.path = os.path.join(self.root_path, str(self.cube))
        self.options = options

        self.index = index.open_dir(self.path)
        self.searcher = self.index.searcher()
        self.default_limit = default_limit or 20
        self.locales = locales or []

    def search(self, query, dimension=None, locale=None, limit=None):
        """Peform search using Whoosh. If `dimension` is set then only the one
        dimension will be searched."""
        print "SEARCH IN %s QUERY '%s' LOCALE:%s" % (str(dimension), query, locale)

        qp = QueryParser("value", schema=self.index.schema)

        q = qp.parse(query)
        if dimension:
            q = q & Term('dimension', str(dimension))

        if locale:
            q = q & Term('locale', str(locale))
        # FIXME: set locale filter

        facet = FieldFacet("value")
        limit = limit or self.default_limit
        print "QUERY: %s" % q
        results = self.searcher.search(q, limit=limit, sortedby=facet)

        print "FOUND: %s results" % len(results)
        return WhooshSearchResult(self.browser, results)


class WhooshSearchResult(object):
    def __init__(self, browser, results):
        super(WhooshSearchResult, self).__init__()
        self.browser = browser
        self.results = results
        self.total_found = len(results)
        self.error = None
        self.warning = None

    # @property
    # def dimensions(self):
    #     return self.dimension_paths.keys()

    def dimension_matches(self, dimension):
        matches = []
        dim_name = str(dimension)
        for match in self.results:
            if match["dimension"] == dim_name:
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
