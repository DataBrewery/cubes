# -*- encoding: utf8 -*-

"""Cubes Modeler – experimental Flask app.

Note: Use only as local server with slicer:

    slicer model edit MODEL [TARGET]

"""

from flask import Flask, render_template, request
from cubes import Model, read_model_metadata, create_model_provider
from cubes import get_logger, write_model_metadata_bundle
from cubes import fix_dimension_metadata
import json
from collections import OrderedDict
from itertools import count

modeler = Flask(__name__, static_folder='static', static_url_path='')

# TODO: maybe we should not have these as globals
# Model:
CUBES = OrderedDict()
DIMENSIONS = OrderedDict()
MODEL = {}
SOURCE = None

cube_id_sequence = count(1)
dimension_id_sequence = count(1)

saved_model_filename = "saved_model.cubesmodel"

def import_model(path):
    # We need to use both: the metadata and the created model, as we do not
    # want to reproduce the model creation here
    global MODEL

    cube_id_sequence = count(1)
    dimension_id_sequence = count(1)

    logger = get_logger()
    logger.setLevel("INFO")
    logger.info("importing model from %s" % path)

    metadata = read_model_metadata(path)

    cube_list = metadata.pop("cubes", [])
    for i, cube in enumerate(cube_list):
        cube_id = cube_id_sequence.next()
        cube["id"] = cube_id
        CUBES[str(cube_id)] = cube

    dim_list = metadata.pop("dimensions", [])
    for i, dim in enumerate(dim_list):
        dim = fix_dimension_metadata(dim)

        dim_id = dimension_id_sequence.next()
        dim["id"] = dim_id
        DIMENSIONS[str(dim_id)] = dim

    MODEL = metadata

    # Convert joins (of known types)
    # TODO: currently we assume that all JOINS are SQL joins as we have no way
    # to determine actual store and therefore the backend used for
    # interpreting this model

    joins = metadata.pop("joins", [])

    for join in joins:
        if "detail" in join:
            join["detail"] = _fix_sql_join_value(join["detail"])
        if "master" in join:
            join["master"] = _fix_sql_join_value(join["master"])
        join["__type__"] = "sql"

    MODEL["joins"] = joins


def _fix_sql_join_value(value):
    if isinstance(value, basestring):
        split = value.split(".")
        if len(split) > 1:
            join = {
                "table": split[0],
                "column": ".".join(split[1:])
            }
        else:
            join = {"column":value}
        return join
    else:
        return value


def save_model():
    model = dict(MODEL)
    model["cubes"] = list(CUBES.values())
    model["dimensions"] = list(DIMENSIONS.values())

    # with open(SAVED_MODEL_FILENAME, "w") as f:
    #     json.dump(model, f, indent=4)

    write_model_metadata_bundle(saved_model_filename, model, replace=True)


@modeler.route("/")
def index():
    return render_template('index.html')


@modeler.route("/reset")
def reset_model():
    # This is just development reset
    print "Model reset"
    global MODEL, CUBES, DIMENSION

    if SOURCE:
        import_model(SOURCE)
    else:
        cube_id_sequence = count(1)
        dimension_id_sequence = count(1)
        CUBES = OrderedDict()
        DIMENSIONS = OrderedDict()
        MODEL = {}

    return "ok"


@modeler.route("/model")
def get_model():
    # Note: this returns model metadata sans cubes/dimensions
    print MODEL
    return json.dumps(MODEL)


@modeler.route("/model", methods=["PUT"])
def save_model_rq():
    global MODEL
    print request.data
    MODEL = json.loads(request.data)
    save_model()

    return "ok"


@modeler.route("/cubes")
def list_cubes():
    # TODO: return just relevant info
    print json.dumps(CUBES.values())
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


@modeler.route("/cube/<id>", methods=["PUT"])
def save_cube(id):
    cube = json.loads(request.data)
    CUBES[str(id)] = cube
    save_model()

    return "ok"


@modeler.route("/cube/<id>", methods=["GET"])
def get_cube(id):
    info = CUBES[str(id)]

    info["measures"] = fix_attribute_list(info.get("measures"))
    info["aggregates"] = fix_attribute_list(info.get("aggregates"))
    info["details"] = fix_attribute_list(info.get("details"))

    joins = info.pop("joins", [])

    for join in joins:
        if "detail" in join:
            join["detail"] = _fix_sql_join_value(join["detail"])
        if "master" in join:
            join["master"] = _fix_sql_join_value(join["master"])
        join["__type__"] = "sql"

    info["joins"] = joins

    return json.dumps(info)

@modeler.route("/new_cube", methods=["PUT"])
def new_cube():
    cube_id = cube_id_sequence.next()
    cube = {
        "id": cube_id,
        "name": "cube%d" % cube_id,
        "label": "New Cube %s" % cube_id,
        "dimensions": [],
        "aggregates": [],
        "measures": [],
        "mappings": {},
        "joins": [],
        "info": {}
    }

    CUBES[str(cube_id)] = cube

    return json.dumps(cube)


@modeler.route("/dimensions")
def list_dimensions():
    # TODO: return just relevant info
    return json.dumps(DIMENSIONS.values())


@modeler.route("/dimension/<id>", methods=["PUT"])
def save_dimension(id):
    dim = json.loads(request.data)
    DIMENSIONS[str(id)] = dim
    save_model()

    return "ok"


@modeler.route("/dimension/<id>", methods=["GET"])
def get_dimension(id):
    info = DIMENSIONS[str(id)]
    return json.dumps(info)

def run_modeler(source, target="saved_model.cubesmodel", port=5000):
    global saved_model_filename

    saved_model_filename = target

    global SOURCE
    if source:
        import_model(source)
        SOURCE = source

    modeler.run(host="0.0.0.0", port=port, debug=True)

if __name__ == '__main__':
    import sys
    import webbrowser
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        source = None
    run_modeler(source)
