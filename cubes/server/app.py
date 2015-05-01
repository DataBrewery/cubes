# -*- coding: utf-8 -*-

import os
from .base import create_server
from .utils import str_to_bool

# Set the configuration file
try:
    CONFIG_PATH = os.environ["SLICER_CONFIG"]
except KeyError:
    CONFIG_PATH = os.path.join(os.getcwd(), "slicer.ini")

application = create_server(CONFIG_PATH)

debug = os.environ.get("SLICER_DEBUG")
if debug and str_to_bool(debug):
    application.debug = True
