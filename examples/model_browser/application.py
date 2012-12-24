"""Example model browser.

Use:

    python application.py [slicer.ini]

"""

from flask import Flask, render_template, request
import cubes
import argparse
import ConfigParser

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
    cube = model.cubes.values()[0]
    browser = get_browser()
    mapper = browser.mapper
    if dim_name:
        dimension = cube.dimension(dim_name)
        physical = {}
        for attribute in dimension.all_attributes():
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
    if cube_name:
        cube = model.cube(cube_name)
    else:
        cube = model.cubes.values()[0]
    return workspace.browser_for_cube(cube)

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Cubes model browser.')
    parser.add_argument('config', help='server confuguration .ini file')
    parser.add_argument('cube', nargs='?', default=None, help='cube name')
    args = parser.parse_args()

    config = ConfigParser.SafeConfigParser()
    try:
        config.read(args.config)
    except Exception as e:
        raise Exception("Unable to load config: %s" % e)

    cube_name = args.cube

    workspace = cubes.create_workspace_from_config(config)
    model = workspace.model

    app.debug = True
    app.run()
