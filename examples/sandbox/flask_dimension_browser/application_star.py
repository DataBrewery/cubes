from flask import Flask, render_template, request
import cubes

app = Flask(__name__)

#
# Data we aregoing to browse and logical model of the data
#

MODEL_PATH = "model.json"
DB_URL = "sqlite:///data.sqlite"
CUBE_NAME = "irbd_balance"

# Some global variables. We do not have to care about Flask provided thread
# safety here, as they are non-mutable.

workspace = None
model = None

@app.route("/")
@app.route("/<dim_name>")
def report(dim_name=None):
    global model
    browser = get_browser()

    if not dim_name:
        return render_template('report_star.html', dimensions=model.dimensions)

    # First we need to get the hierarchy to know the order of levels. Cubes
    # supports multiple hierarchies internally.
    
    dimension = model.dimension(dim_name)
    hierarchy = dimension.hierarchy()

    # Parse the`cut` request parameter and convert it to a list of 
    # actual cube cuts. Think of this as of multi-dimensional path, even that 
    # for this simple example, we are goint to use only one dimension for
    # browsing.

    cutstr = request.args.get("cut")
    cell = cubes.Cell(browser.cube, cubes.cuts_from_string(cutstr))

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
        breadcrumbs = browser.cell_details(cell, dimension)[0]
    else:
        breadcrumbs = {}

    # Find what level we are on and what is going to be the drill-down level
    # in the hierarchy
    
    levels = hierarchy.levels_for_path(path)
    if levels:
        next_level = hierarchy.next_level(levels[-1])
    else:
        next_level = hierarchy.levels[0]
    
    # To have human-readable table, we are not going to display keys or codes,
    # but actual human-readable labels that are also stored within dimension.
    # The dimension provides information in which attribute the label is
    # stored.
    
    label_attribute = next_level.label_attribute.ref(simplify=True)

    # We also need to know key attribute for the level, so we can generate
    # appropriate URL links with cut of drilled-down cells.

    key = next_level.key.ref(simplify=True)

    # Are we at the very detailed level?

    is_last = len(path) >= len(hierarchy.levels)-1

    # Finally, we render it

    return render_template('report_star.html', 
                            dimensions=model.dimensions, 
                            dimension=dimension,
                            levels=levels, 
                            next_level=next_level, 
                            label_attribute=label_attribute, 
                            level_key=key,
                            result=result, 
                            cell=cell, is_last=is_last,
                            breadcrumbs=breadcrumbs)

def initialize_model():
    global workspace
    global model

    model = cubes.load_model(MODEL_PATH)
    workspace = cubes.create_workspace("sql", model, url=DB_URL,
                                                     fact_prefix="ft_")

def get_browser():
    return workspace.browser_for_cube(model.cube(CUBE_NAME))

if __name__ == "__main__":
    app.debug = True
    initialize_model()
    app.run()
