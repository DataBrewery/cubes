# -*- coding: utf-8 -*-
from .blueprint import slicer
from flask import Flask
import ConfigParser
import shlex

from .utils import *

__all__ = (
    "create_server",
    "run_server"
)

# Server Instantiation and Running
# ================================

def _read_config(config):
    if not config:
        return ConfigParser.SafeConfigParser()
    elif isinstance(config, basestring):
        try:
            path = config
            config = ConfigParser.SafeConfigParser()
            config.read(path)
        except Exception as e:
            raise Exception("Unable to load configuration: %s" % e)
    return config

def create_server(config=None):
    """Returns a Flask server application. `config` is a path to a
    ``slicer.ini`` file with Cubes workspace and server configuration."""

    config = read_server_config(config)

    # Load extensions

    if config.has_option("server", "modules"):
        modules = shlex.split(config.get("server", "modules"))
        for module in modules:
            e = __import__(module)

    app = Flask("slicer")
    app.register_blueprint(slicer, config=config)

    return app


def run_server(config, debug=False):
    """Run OLAP server with configuration specified in `config`"""

    config = read_server_config(config)
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

    app.run(host, port, debug=debug, processes=processes,
            use_reloader=use_reloader)

