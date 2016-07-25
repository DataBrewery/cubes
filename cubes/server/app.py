# -*- coding: utf-8 -*-

import os
from .base import create_server
from .base import read_slicer_config
from .utils import str_to_bool

# Set the configuration file
try:
    CONFIG_PATH = os.environ["SLICER_CONFIG"]
except KeyError:
    CONFIG_PATH = os.path.join(os.getcwd(), "slicer.ini")

config = read_slicer_config(CONFIG_PATH)
application = create_server(config)

debug = os.environ.get("SLICER_DEBUG")
if debug and str_to_bool(debug):
    application.debug = True
