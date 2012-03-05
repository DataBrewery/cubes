"""This backend is just an example of a backend. Uses another Slicer server 
instance for doing all the work. You might use it as a template for your own
browser."""

from browser import *

__all__ = ["SlicerBrowser"]

def create_workspace(model, config):
    """Create workspace for `model` with configuration in dictionary `config`. 
    This method is used by the slicer server."""

    try:
        url = config["url"]
    except KeyError:
        raise Exception("No URL specified in configuration")

    workspace = Workspace(model, url)

    return workspace

class Workspace(object):
    """Factory for browsers"""
    def __init__(self, model, url):
        """Create a workspace"""
        super(Workspace, self).__init__()
        self.model = model
        self.url = url
        
    def browser_for_cube(self, cube, locale = None):
        """Creates, configures and returns a browser for a cube"""
        cube = self.model.cube(cube)
        browser = SlicerBrowser(cube, self.url, locale = locale)
        return browser
