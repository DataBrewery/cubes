import logging
import sys

__all__ = [
    "logger_name",
    "get_logger",
    "create_logger",
    "IgnoringDictionary",
    "MissingPackage"
]

logger_name = "cubes"
logger = None

def get_logger():
    """Get brewery default logger"""
    global logger
    
    if logger:
        return logger
    else:
        return create_logger()
        
def create_logger():
    """Create a default logger"""
    global logger
    logger = logging.getLogger(logger_name)

    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s')
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

class IgnoringDictionary(dict):
    """Simple dictionary extension that will ignore any keys of which values
    are empty (None/False)"""
    def setnoempty(self, key, value):
        """Set value in a dictionary if value is not null"""
        if value:
            self[key] = value

class MissingPackage(object):
    """Bogus class to handle missing optional packages - packages that are not
    necessarily required for Cubes, but are needed for certain features."""

    def __init__(self, package, feature = None, source = None, comment = None):
        self.package = package
        self.feature = feature
        self.source = source
        self.comment = comment

    def __call__(self, *args, **kwargs):
        self._fail()

    def __getattr__(self, name):
        self._fail()

    def _fail(self):
        if self.feature:
            use = " to be able to use: %s" % self.feature
        else:
            use = ""

        if self.source:
            source = " from %s" % self.source
        else:
            source = ""

        if self.comment:
            comment = ". %s" % self.comment
        else:
            comment = ""

        raise Exception("Optional package '%s' is not installed. Please install the package%s%s%s" % 
                            (self.package, source, use, comment))
