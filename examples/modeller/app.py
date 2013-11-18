from flask import Flask, render_template, request
from flask_wtf import Form
from wtforms import TextField, TextAreaField, SelectField
from database import Cube, Dimension, Level
from database import db_session, Cube, Dimension, Level
from flask import redirect, url_for
from wtforms.ext.sqlalchemy.orm import model_form
from cubes import read_model_metadata
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///modeller.sqlite"
app.config['CSRF_ENABLED'] = False
app.config['SECRET_KEY'] = "This is very secret"

class CubeForm(Form):
    name = TextField('Name')
    label = TextField('Label')
    info = TextAreaField('Info (JSON)')
    description = TextAreaField('Description')

class DimensionForm(Form):
    name = TextField('Name')
    label = TextField('Label')
    info = TextAreaField('Info (JSON)')
    description = TextAreaField('Description')
    role = SelectField('Role', choices=[('default', 'default'),
                                        ('time', 'time')])

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.route("/")
def index():
    cubes = db_session.query(Cube).all()
    dimensions = db_session.query(Dimension).all()
    return render_template("index.html",
                           cubes=cubes,
                           dimensions=dimensions)

@app.route("/cube", methods=["GET", "POST"],
                         defaults={"cube_id":None})
@app.route("/cube/<cube_id>", methods=["GET", "POST"])
def edit_cube(cube_id):

    if request.method == "POST":
        if cube_id:
            cube = db_session.query(Cube).get(cube_id)
        else:
            cube = Cube()
            db_session.add(cube)

        cube.name = request.values.get("name")
        cube.label = request.values.get("label")
        cube.description = request.values.get("description")
        cube.info = request.values.get("info")

        db_session.commit()

        return redirect(url_for("index"))
    else:
        if cube_id:
            cube = db_session.query(Cube).get(cube_id)
            form = CubeForm(obj=cube)
        else:
            form = CubeForm()

        return render_template("edit_cube.html", form=form, cube_id=cube_id)


@app.route("/delete_cube/<cube_id>")
def delete_cube(cube_id):
    cube = db_session.query(Cube).get(cube_id)
    db_session.delete(cube)
    db_session.commit()

    return redirect(url_for("index"))


@app.route("/dimension", methods=["GET", "POST"],
                         defaults={"dimension_id":None})
@app.route("/dimension/<dimension_id>", methods=["GET", "POST"])
def edit_dimension(dimension_id):

    if request.method == "POST":
        if dimension_id:
            dimension = db_session.query(Dimension).get(dimension_id)
        else:
            dimension = Dimension()
            db_session.add(dimension)

        dimension.name = request.values.get("name")
        dimension.label = request.values.get("label")
        dimension.description = request.values.get("description")
        dimension.info = request.values.get("info")

        role = request.values.get("role")
        if role and role != "default":
            dimension.role = role
        else:
            dimension.role = None

        db_session.commit()

        return redirect(url_for("index"))
    else:
        if dimension_id:
            dimension = db_session.query(Dimension).get(dimension_id)
            form = DimensionForm(obj=dimension)
        else:
            form = DimensionForm()

        return render_template("edit_dimension.html", form=form,
                                dimension_id=dimension_id)

@app.route("/delete_dimension/<dimension_id>")
def delete_dim(dimension_id):
    dim = db_session.query(Dimension).get(dimension_id)
    db_session.delete(dim)
    db_session.commit()

    return redirect(url_for("index"))

def load_model(path):
    metadata = read_model_metadata(path)

    db_session.query(Cube).delete()
    db_session.query(Dimension).delete()
    db_session.query(Level).delete()

    for obj in metadata.get("cubes", []):
        print "adding cube %s" % obj["name"]

        cube = Cube()
        cube.name = obj.get("name")
        cube.label = obj.get("label")
        cube.description = obj.get("description")
        if "info" in obj:
            cube.info = json.dumps(obj.get("info"))
        db_session.add(cube)

    for obj in metadata.get("dimensions", []):
        dim = Dimension()
        dim.name = obj.get("name")
        dim.label = obj.get("label")
        dim.description = obj.get("description")
        dim.role = obj.get("role")
        if "info" in obj:
            dim.info = json.dumps(obj.get("info"))
        print "adding dimension %s" % dim.name
        db_session.add(dim)

    db_session.commit()

if __name__ == "__main__":

    import sys

    if len(sys.argv) > 1:
        load_model(sys.argv[1])

    app.run(debug=True)
