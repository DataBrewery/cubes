"""Multidimensional searching using Sphinx search engine"""
import cubes.browser as browser
import sphinxapi
import xml.sax.saxutils
from xml.sax.xmlreader import AttributesImpl

EMPTY_ATTRS = AttributesImpl({})

class SphinxSearchResult(object):
    def __init__(self, browser):
        super(SphinxSearchResult, self).__init__()
        self.browser = browser
        self.dimension_paths = None
        self.total_found = None
        
    @property
    def dimensions(self):
        return self.dimension_paths.keys()
        
    def values(self, dimension):
        cell = self.browser.full_cube()
        paths = self.dimension_paths[dimension]

        cut = cubes.browser.SetCut(dim, paths)
        cell.cuts = [cut]
        return cell.values(dimension)

class SphinxSearch(object):
    """docstring for SphinxSearch"""
    def __init__(self, browser, host = None, port = None):
        """Create sphing search object.
        
        :Parameters:
            * `browser` - Aggregation browser
            * `host` - host where searchd is running (optional)
            * `port` - port where searchd is listening (optional)
        """
        super(SphinxSearch, self).__init__()
        self.browser = browser
        self.config = config
        self.host = host
        self.port = port
        
    def _dimension_tag(self, dimension):
        tag = None
        tdim = self.browser.cube.dimension(dimension)
        for i, dim in enumerate(self.browser.cube.dimensions):
            if dim.name == tdim.name:
                tag = i
                break
        return tag

    def search(self, query, dimension = None):
        """Peform search using Sphinx. If `dimension` is set then only the one dimension will
        be searched."""
        
        sphinx = sphinxapi.SphinxClient(**self.config)

        if self.host:
            sphinx.SetServer(self.host, self.port)

        if dimension:
            tag = self._dimension_tag(dimension)
            if not tag:
                raise Exception("No dimension %s" % dimension)
            print "SETTING TAG: %s" % tag
            sphinx.SetFilter("dimension_tag", [tag])

        results = sphinx.Query(query)

        result = SphinxSearchResult(browser)

        if not results:
            print "NOTHING FOUND"
            return result

        result.total_found = results["total_found"]

        grouped = collections.OrderedDict()

        for match in results["matches"]:
            attrs = match["attrs"]
            key = tuple( (attrs["dimension"], attrs["path"]) )

            if key in grouped:
                exmatch = grouped[key]
                exattrs = exmatch["attributes"]
                exattrs.append(attrs["attribute"])
            else:
                exmatch = {"attributes": [attrs["attribute"]]}
                grouped[key] = exmatch
        
        paths = collections.OrderedDict()
        for (key, attrs) in grouped.items():
            (dim, path_str) = key
            path = cubes.browser.path_from_string(path_str)
            if dim in paths:
                paths[dim].append(path)
            else:
                paths[dim] = [path]
    
        result.dimension_paths = paths

        return result
        
class SphinxIndexer(object):
    """docstring for Indexer"""
    def __init__(self, browser, out = None):
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
        super(Indexer, self).__init__()

        self.browser = browser
        self.cube = browser.cube
        
        self.output = xml.sax.saxutils.XMLGenerator(out = out, encoding = 'utf-8')
        self._counter = 1
        
    def _preamble(self):
        self.output.startDocument()

        self.output.startElement( u'sphinx:docset', EMPTY_ATTRS)

        # START schema
        self.output.startElement( u'sphinx:schema', EMPTY_ATTRS)  

        fields = ["value"]
                  
        attributes = [("dimension", "string"), 
                      ("dimension_tag", "int"),
                        ("level", "string"), 
                        ("depth", "int"), 
                        ("path", "string"), 
                        ("attribute", "string"), 
                        ("level_key", "string"), 
                        ("level_label", "string")]

        for field in fields:
            attrs = AttributesImpl({"name":field})
            self.output.startElement( u'sphinx:field', attrs)
            self.output.endElement(u'sphinx:field')

        for (name, ftype) in attributes:
            attrs = AttributesImpl({"name":name, "type":ftype})
            self.output.startElement( u'sphinx:attr', attrs)
            self.output.endElement(u'sphinx:attr')

        # END schema
        self.output.endElement(u'sphinx:schema')

    def _epilogue(self):
        self.output.endElement( u'sphinx:docset')
        self.output.endDocument()
        
    def index(self):
        """Create index records for all dimensions in the cube"""
        # FIXME: this works only for one locale - specified in browser
        
        # for dimension in self.cube.dimensions:
        self._preamble()
        
        for i, dimension in enumerate(self.cube.dimensions):
            # dimension = self.cube.dimension("program")
            self.index_dimension(dimension, i)
        self._epilogue()
            
    def index_dimension(self, dimension, dimension_tag, hierarchy = None):
        """Create dimension index records."""
        
        if not hierarchy:
            hierarchy = dimension.default_hierarchy
            
        cuboid = self.browser.full_cube()
        
        for depth_m1, level in enumerate(hierarchy.levels):
            depth = depth_m1 + 1

            levels = hierarchy.levels[0:depth]
            keys = [(dimension.name + "." + l.key.name) for l in levels]
            level_key = keys[-1]
            level_label = (dimension.name + "." + level.label_attribute.name)
            for record in cuboid.values(dimension, depth):
                path = [record[key] for key in keys]
                path_string = browser.string_from_path(path)
                for attr in level.attributes:
                    fname = attr.full_name(dimension)
                    irecord = { 
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
                    self.emit(irecord)

    def emit(self, irecord):
        """Emits index record (sphinx document) to the output XML stream."""
        
        attrs = AttributesImpl({"id":str(self._counter)})
        self._counter += 1

        self.output.startElement( u'sphinx:document', attrs)

        attrs = AttributesImpl({})
        for key, value in irecord.items():
            self.output.startElement( key, attrs)
            self.output.characters(unicode(value))
            self.output.endElement(key)

        self.output.endElement( u'sphinx:document')
        
        
    