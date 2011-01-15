"""OLAP Cubes"""

from base import *

from cubes.model import *
from cubes.view_builder import *
from cubes.aggregation_browser import *

from cubes.mongo import *
import utils

# Initialize logging

import logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
                    # datefmt='%a, %d %b %Y %H:%M:%S',
                    
