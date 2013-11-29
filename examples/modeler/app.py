from flask import Flask, render_template, request
from cubes import Model, read_model_metadata, create_model_provider
from cubes import get_logger, write_model_metadata_bundle
from cubes import fix_dimension_metadata
import json
from collections import OrderedDict

app = Flask(__name__, static_folder='static', static_url_path='')

# Model:
CUBES = OrderedDict()
DIMENSIONS = OrderedDict()
MODEL = {}

SAVED_MODEL_FILENAME = "saved_model.cubesmodel"

def import_model(path):
    # We need to use both: the metadata and the created model, as we do not
    # want to reproduce the model creation here
    global MODEL

    logger = get_logger()
    logger.setLevel("INFO")
    logger.info("importing model from %s" % path)

    metadata = read_model_metadata(path)

    cube_list = metadata.pop("cubes", [])
    for i, cube in enumerate(cube_list):
        cube_id = i + 1
        cube["id"] = cube_id
        CUBES[str(cube_id)] = cube

    dim_list = metadata.pop("dimensions", [])
    for i, dim in enumerate(dim_list):
        dim = fix_dimension_metadata(dim)
        dim_id = i + 1
        dim["id"] = dim_id
        DIMENSIONS[str(dim_id)] = dim

    MODEL = metadata

def save_model():
    model = dict(MODEL)
    model["cubes"] = list(CUBES.values())
    model["dimensions"] = list(DIMENSIONS.values())

    # with open(SAVED_MODEL_FILENAME, "w") as f:
    #     json.dump(model, f, indent=4)

    write_model_metadata_bundle(SAVED_MODEL_FILENAME, model, replace=True)

@app.route("/")
def index():
    return render_template('index.html')


@app.route("/cubes")
def list_cubes():
    # TODO: return just relevant info
    return json.dumps(CUBES.values())


def fix_attribute_list(attributes):
    if not attributes:
        return []

    fixed = []
    for attribute in attributes:
        if isinstance(attribute, basestring):
            attribute = {"name": attribute}
        fixed.append(attribute)

    return fixed


@app.route("/cube/<id>", methods=["PUT"])
def save_cube(id):
    cube = json.loads(request.data)
    CUBES[str(id)] = cube
    save_model()

    return "ok"


@app.route("/cube/<id>", methods=["GET"])
def get_cube(id):
    info = CUBES[str(id)]

    info["measures"] = fix_attribute_list(info.get("measures"))
    info["aggregates"] = fix_attribute_list(info.get("aggregates"))
    info["details"] = fix_attribute_list(info.get("details"))

    return json.dumps(info)


@app.route("/dimensions")
def list_dimensions():
    # TODO: return just relevant info
    return json.dumps(DIMENSIONS.values())


@app.route("/dimension/<id>", methods=["PUT"])
def save_dimension(id):
    dim = json.loads(request.data)
    DIMENSIONS[str(id)] = dim
    save_model()

    return "ok"


@app.route("/dimension/<id>", methods=["GET"])
def get_dimension(id):
    info = DIMENSIONS[str(id)]
    return json.dumps(info)



if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        import_model(sys.argv[1])

    app.run(debug=True)
