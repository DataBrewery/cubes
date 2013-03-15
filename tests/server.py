import unittest
import flask
import sqlalchemy
import cubes
from flask import Flask
from sqlalchemy import Table, Column, Integer, Float, String
from cubes.backends import SnowflakeBrowser


class FlaskTest(unittest.TestCase):
    def setUp(self):
        engine = sqlalchemy.create_engine('sqlite://')
        desc = {"dimensions": ["date", "product", "flag"]}
        model = cubes.create_model(desc)
        workspace = cubes.create_workspace('sql', model, engine=engine)

        self.app = Flask(__name__)
        self.app.register_blueprint(cubes.server.slicer_blueprint)
        self.app.workspace = workspace
        self.client = self.app.test_client()

    def test_display(self):
        response = self.client.get('/')
        self.assertEqual(200, response.status_code)