import cubes.browser
import urllib2
import json
import logging
import urllib

class SlicerBrowser(cubes.browser.AggregationBrowser):
    """Aggregation browser for Cubes Slicer OLAP server."""
    
    def __init__(self, url, cube):
        """Create a browser.
        
        :Attributes:
            * `cube` - name of a cube
            * `url` - base url of Cubes Slicer OLAP server

        """
        super(SlicerBrowser, self).__init__(cube)

        self.cube_name = cube
        self.baseurl = url

        self.logger = logging.getLogger("brewery.cubes")
    
        self.model = None
        self.cube = None
        
        self._load_model()
        
    def _load_model(self):
        url = self.baseurl + "/model"

        dictionary = self.request(url)
        try:
            self.model = cubes.model_from_dict(dictionary)
        except Exception as e:
            raise Exception("Unable to create model from response. Reason: %s" % e)

        self.cube = self.model.cube(self.cube_name)

    def request(self, url):
        handle = urllib2.urlopen(url)
        try:
            reply = json.load(handle)
        except Exception as e:
            raise Exception("Unable to load request %s. Reason: %s" % (url, e))
        finally:
            handle.close()
        
        return reply            
                
    def aggregate(self, cuboid, measures = None, drilldown = None):
        """See :meth:`cubes.browsers.Cuboid.aggregate`."""
        result = cubes.base.AggregationResult()
        
        cut_string = cubes.base.string_from_cuts(cuboid.cuts)
        params = [ ("cut", cut_string) ]
        if drilldown:
            for dd in drilldown:
                params.append( ("drilldown", dd) )
                
        url = self.baseurl + "/aggregate?" + urllib.urlencode(params)
        
        return self.request(url)
        
    def facts(self, cuboid, **options):
        raise NotImplementedError

    def fact(self, key):
        """Fetch single row based on fact key"""

        url = self.baseurl + "/fact/" + urllib.quote(str(key))
        return self.request(url)
