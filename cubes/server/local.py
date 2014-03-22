# -*- coding: utf-8 -*-
from flask import current_app
from werkzeug.local import LocalProxy

# Application Context
# ===================
#
# Readability proxies

def _get_workspace():
    return current_app.cubes_workspace

def _get_logger():
    return current_app.cubes_workspace.logger

workspace = LocalProxy(_get_workspace)
logger = LocalProxy(_get_logger)

