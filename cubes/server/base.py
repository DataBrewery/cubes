# -*- encoding: utf-8 -*-

from __future__ import absolute_import
from .blueprint import slicer
from flask import Flask
import shlex
import os

from .utils import *
from .. import compat
from ..logging import get_logger

__all__ = (
    "create_server",
    "run_server"
)

# Server Instantiation and Running
# ================================

def read_slicer_config(config):
    if not config:
        return compat.ConfigParser()
    elif isinstance(config, compat.string_type):
        try:
            path = config
            config = compat.ConfigParser()
            config.read(path)
        except Exception as e:
            raise Exception("Unable to load configuration: %s" % e)
    return config

def create_server(config=None, **_options):
    """Returns a Flask server application. `config` is a path to a
    ``slicer.ini`` file with Cubes workspace and server configuration."""

    # Load extensions
    if config.has_option("server", "modules"):
        modules = shlex.split(config.get("server", "modules"))
        for module in modules:
            e = __import__(module)

    app = Flask(__name__.rsplit('.', 1)[0])
    # FIXME: read note about _options in Workspace. Only for internal use as a
    # temporary quick fix.
    app.register_blueprint(slicer, config=config, **_options)

    return app

def run_server(config, debug=False, app=None):
    """Run OLAP server with configuration specified in `config`"""

    config = read_slicer_config(config)

    logger = get_logger()

    if config.has_option("server", "debug"):
        if debug is False and config.getboolean("server", "debug"):
            debug = True

    if debug:
        logger.warning('Server running under DEBUG, so logging level set to DEBUG.')
        import logging
        logger.setLevel(logging.DEBUG)

    if app is None:
        app = create_server(config)

    if config.has_option("server", "host"):
        host = config.get("server", "host")
    else:
        host = "localhost"

    if config.has_option("server", "port"):
        port = config.getint("server", "port")
    else:
        port = 5000

    if config.has_option("server", "reload"):
        use_reloader = config.getboolean("server", "reload")
    else:
        use_reloader = False

    if config.has_option('server', 'processes'):
        processes = config.getint('server', 'processes')
    else:
        processes = 1

    if config.has_option("server", "pid_file"):
        path = config.get("server", "pid_file")
        try:
            with open(path, "w") as f:
                f.write(str(os.getpid()))
        except IOError as e:
            logger.error("Unable to write PID file '%s'. Check the "
                         "directory existence or permissions." % path)
            raise

    app.run(host, port, debug=debug, processes=processes,
            use_reloader=use_reloader)

