# -*- encoding: utf-8 -*-

from __future__ import absolute_import
from .blueprint import slicer
from flask import Flask
import shlex

from .utils import *
from .. import compat

__all__ = (
    "create_server",
    "run_server"
)

# Server Instantiation and Running
# ================================

def _read_config(config):
    if not config:
        return compat.configparser.SafeConfigParser()
    elif isinstance(config, compat.string_type):
        try:
            path = config
            config = compat.configparser.SafeConfigParser()
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

    app = Flask(__name__)
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

