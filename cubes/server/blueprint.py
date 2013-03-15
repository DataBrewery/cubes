import cubes
import flask
from werkzeug.local import LocalProxy

API_VERSION = "1"

app = flask.Blueprint('slicer', __name__, template_folder='templates')
workspace = LocalProxy(lambda:flask.current_app.workspace)
model = LocalProxy(lambda:workspace.localized_model(flask.request.args.get('lang')))

@app.context_processor
def _server_info():
    info = {
        "version": cubes.__version__,
        # Backward compatibility key
        "server_version": cubes.__version__,
        "api_version": API_VERSION
    }


    return info


@app.route('/')
def index():
    array = [cube.name for cube in model.cubes.values()]
    if array:
        cubes = ", ".join(array)
    else:
        cubes = "<none>"

    return flask.render_template(
        'index.html',
        model=model.name,
        cubes=cubes
    )