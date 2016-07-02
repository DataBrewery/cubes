"""Example model browser.

Use:

    python application.py [slicer.ini]

"""

import argparse
import ConfigParser

from cubes import Workspace
from flask import Flask, render_template

app = Flask(__name__)

#
# Data we aregoing to browse and logical model of the data
#

# Some global variables. We do not have to care about Flask provided thread
# safety here, as they are non-mutable.

workspace = None
model = None
cube_name = None


@app.route("/")
@app.route("/<dim_name>")
def report(dim_name=None):
    browser = get_browser()
    cube = browser.cube
    mapper = browser.mapper
    if dim_name:
        dimension = cube.dimension(dim_name)
        physical = {}
        for attribute in dimension.attributes:
            logical = attribute.ref()
            physical[logical] = mapper.physical(attribute)
    else:
        dimension = None
        physical = None

    return render_template('index.html',
                           dimensions=cube.dimensions,
                           dimension=dimension,
                           mapping=physical)


def get_browser():
    global cube_name
    if not cube_name:
        # Get the first cube in the list
        cubes = workspace.list_cubes()
        cube_name = cubes[0]["name"]

    return workspace.browser(cube_name)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Cubes model browser.')
    parser.add_argument('config', help='server configuration .ini file')
    parser.add_argument('cube', nargs='?', default=None, help='cube name')
    args = parser.parse_args()

    config = ConfigParser.SafeConfigParser()
    try:
        config.read(args.config)
    except Exception as e:
        raise Exception("Unable to load config: %s" % e)

    cube_name = args.cube

    workspace = Workspace(config)

    app.debug = True
    app.run()
