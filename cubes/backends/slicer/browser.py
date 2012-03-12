# -*- coding=utf -*-

import cubes.browser
import urllib2
import json
import logging
import urllib

class SlicerBrowser(cubes.browser.AggregationBrowser):
    """Aggregation browser for Cubes Slicer OLAP server."""
    
    def __init__(self, cube, url, locale = None):
        """Demo backend browser. This backend is serves just as example of a 
        backend. Uses another Slicer server instance for doing all the work. 
        You might use it as a template for your own browser.

        Attributes:

        * `cube` – obligatory, but currently unused here
        * `url` - base url of Cubes Slicer OLAP server

        """
        super(SlicerBrowser, self).__init__(cube)

        self.logger = logging.getLogger("brewery.cubes")

        self.baseurl = url
        self.cube = cube
        
    def request(self, url):
        handle = urllib2.urlopen(url)
        try:
            reply = json.load(handle)
        except Exception as e:
            raise Exception("Unable to load request %s. Reason: %s" % (url, e))
        finally:
            handle.close()
        
        return reply            
                
    def aggregate(self, cell, measures = None, drilldown = None, **kwargs):
        result = cubes.AggregationResult()
        
        cut_string = cubes.browser.string_from_cuts(cell.cuts)
        params = [ ("cut", cut_string) ]
        if drilldown:
            for dd in drilldown:
                params.append( ("drilldown", dd) )
                
        url = self.baseurl + "/aggregate?" + urllib.urlencode(params)
        
        return self.request(url)
        
    def facts(self, cell, **options):
        raise NotImplementedError

    def fact(self, key):

        url = self.baseurl + "/fact/" + urllib.quote(str(key))
        return self.request(url)
