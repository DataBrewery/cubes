from flask import Flask, render_template
from cubes import Model, read_model_metadata, create_model_provider
from cubes import get_logger
import json

app = Flask(__name__, static_folder='static', static_url_path='')

model = Model(provider=create_model_provider("static", {}))

cube_list = {}
cube_infos = {}
cubes = {}

def import_model(path):
    # We need to use both: the metadata and the created model, as we do not
    # want to reproduce the model creation here
    global model, cube_list

    logger = get_logger()

    metadata = read_model_metadata(path)
    provider = create_model_provider("static", metadata)

    model = Model(provider=provider, metadata=metadata)

    cube_list = provider.list_cubes()
    for i, cube in enumerate(cube_list):
        id = i + 1
        cube["id"] = id
        cube_infos[str(id)] = cube

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/cubes")
def list_cubes():
    return json.dumps(cube_list)

@app.route("/cube/<id>")
def get_cube(id):
    info = cube_infos[str(id)]
    # TODO: use raw metadata
    cube = model.provider.cube(info["name"])
    return json.dumps(cube.to_dict())



if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        import_model(sys.argv[1])

    app.run(debug=True)
