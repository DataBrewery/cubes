from flask import Flask, render_template, request
from flask_wtf import Form
from wtforms import TextField, TextAreaField
from database import Cube, Dimension, Level
from database import db_session, Cube, Dimension, Level
from flask import redirect, url_for
from wtforms.ext.sqlalchemy.orm import model_form

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///modeller.sqlite"
app.config['CSRF_ENABLED'] = False
app.config['SECRET_KEY'] = "This is very secret"

class CubeForm(Form):
    name = TextField('Name')
    label = TextField('Label')
    info = TextAreaField('Info (JSON)')
    description = TextAreaField('Description')

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

@app.route("/")
def index():
    cubes = db_session.query(Cube).all()
    return render_template("index.html",
                           cubes=cubes)

@app.route("/edit_cube", methods=["GET", "POST"],
                         defaults={"cube_id":None})
@app.route("/edit_cube/<cube_id>", methods=["GET", "POST"])
def edit_cube(cube_id):

    if request.method == "POST":
        if cube_id:
            is_new = False
            cube = db_session.query(Cube).get(cube_id)
        else:
            is_new = True
            cube = Cube()

        cube.name = request.values.get("name")
        cube.label = request.values.get("label")
        cube.description = request.values.get("description")
        cube.info = request.values.get("info")

        if is_new:
            db_session.add(cube)

        db_session.commit()

        return redirect(url_for("index"))
    else:
        if cube_id:
            is_new = False
            cube = db_session.query(Cube).get(cube_id)
            form = CubeForm(obj=cube)
        else:
            is_new = True
            form = CubeForm()

        return render_template("edit_cube.html", form=form, cube_id=cube_id)

@app.route("/delete_cube/<cube_id>")
def new_cube(cube_id):
    cube = db_session.query(Cube).get(cube_id)
    db_session.delete(cube)
    db_session.commit()

    return redirect(url_for("index"))

if __name__ == "__main__":

    app.run(debug=True)
