from flask import Flask, render_template
from cubes import Model, read_model_metadata, create_model_provider
from cubes import get_logger
import json
from collections import OrderedDict

app = Flask(__name__, static_folder='static', static_url_path='')

# Model:
CUBES = OrderedDict()
DIMENSIONS = OrderedDict()

def import_model(path):
    # We need to use both: the metadata and the created model, as we do not
    # want to reproduce the model creation here
    global model, cube_list

    logger = get_logger()

    metadata = read_model_metadata(path)

    cube_list = metadata.get("cubes", [])
    for i, cube in enumerate(cube_list):
        cube_id = i + 1
        cube["id"] = cube_id
        CUBES[str(cube_id)] = cube

    dim_list = metadata.get("dimensions", [])
    for i, dim in enumerate(dim_list):
        dim_id = i + 1
        dim["id"] = dim_id
        DIMENSIONS[str(dim_id)] = dim

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/cubes")
def list_cubes():
    # TODO: return just relevant info
    return json.dumps(CUBES.values())

@app.route("/cube/<id>")
def get_cube(id):
    info = CUBES[str(id)]
    return json.dumps(info)

@app.route("/dimensions")
def list_dimensions():
    # TODO: return just relevant info
    return json.dumps(DIMENSIONS.values())

@app.route("/dimension/<id>")
def get_dimension(id):
    info = DIMENSION[str(id)]
    return json.dumps(info)



if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        import_model(sys.argv[1])

    app.run(debug=True)
