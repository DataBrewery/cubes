"""Multidimensional searching"""
import browser
import xml.sax.saxutils
from xml.sax.xmlreader import AttributesImpl

EMPTY_ATTRS = AttributesImpl({})

class Indexer(object):
    """docstring for Indexer"""
    def __init__(self, browser, out = None):
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

        fields = ["dimension", "level", "depth", "path", "attribute", "value", 
                  "level_key", "level_label"]
                  
        for field in fields:
            attrs = AttributesImpl({"name":field})
            self.output.startElement( u'sphinx:field', attrs)
            self.output.endElement(u'sphinx:field')

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
        
        for dimension in self.cube.dimensions:
            # dimension = self.cube.dimension("program")
            self.index_dimension(dimension)
        self._epilogue()
            
    def index_dimension(self, dimension, hierarchy = None):
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
        
        
    