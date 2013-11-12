"""Dimension Browser example

A Flask application for browsing cube's dimensions.

Requirements: run ``python prepare_data.py`` in ``../hello_world``.

Use::
    python application.py

Then navigate your browser to: ``http://localhost:5000``

You can also access the Slicer at ``http://localhost:5000/slicer``.
"""
from flask import Flask, render_template, request, make_response
from cubes import Workspace, Cell, cuts_from_string
from cubes.server import slicer, workspace
from flask import current_app

#
# The Flask Application
#
app = Flask(__name__)

# Cube we are going to browse (only one for this example)
#

CUBE_NAME="irbd_balance"

@app.route("/favicon.ico")
def favicon():
    return make_response("")

@app.route("/")
@app.route("/<dim_name>")
def report(dim_name=None):
    browser = workspace.browser(CUBE_NAME)
    cube = browser.cube

    if not dim_name:
        return render_template('report.html', dimensions=cube.dimensions)

    # First we need to get the hierarchy to know the order of levels. Cubes
    # supports multiple hierarchies internally.

    dimension = cube.dimension(dim_name)
    hierarchy = dimension.hierarchy()

    # Parse the`cut` request parameter and convert it to a list of 
    # actual cube cuts. Think of this as of multi-dimensional path, even that 
    # for this simple example, we are goint to use only one dimension for
    # browsing.

    cutstr = request.args.get("cut")
    cell = Cell(cube, cuts_from_string(cube, cutstr))

    # Get the cut of actually browsed dimension, so we know "where we are" -
    # the current dimension path
    cut = cell.cut_for_dimension(dimension)

    if cut:
        path = cut.path
    else:
        path = []

    #
    # Do the work, do the aggregation.
    #
    result = browser.aggregate(cell, drilldown=[dim_name])

    # If we have no path, then there is no cut for the dimension, # therefore
    # there is no corresponding detail.
    if path:
        details = browser.cell_details(cell, dimension)[0]
    else:
        details = []

    # Find what level we are on and what is going to be the drill-down level
    # in the hierarchy

    levels = hierarchy.levels_for_path(path)
    if levels:
        next_level = hierarchy.next_level(levels[-1])
    else:
        next_level = hierarchy.next_level(None)

    # Are we at the very detailed level?

    is_last = hierarchy.is_last(next_level)
    # Finally, we render it

    return render_template('report.html',
                            dimensions=cube.dimensions,
                            dimension=dimension,
                            levels=levels,
                            next_level=next_level,
                            result=result,
                            cell=cell,
                            is_last=is_last,
                            details=details)


if __name__ == "__main__":

    # Create a Slicer and register it at http://localhost:5000/slicer
    app.register_blueprint(slicer, url_prefix="/slicer", config="slicer.ini")
    app.run(debug=True)


