import unittest
import random
import json
import sqlalchemy
import cubes
from sqlalchemy import Table, Column, Integer, Float, String, MetaData, ForeignKey
from sqlalchemy import create_engine
from cubes.tests import DATA_PATH
import os.path

FACT_COUNT = 100

class SQLBackendTestCase(unittest.TestCase):
    def setUp(self):

        self.view_name = "test_view"
        engine = sqlalchemy.create_engine('sqlite://')
        self.connection = engine.connect()
        self.metadata = sqlalchemy.MetaData()
        self.metadata.bind = engine
        
        years = [2010,2011]

        path = os.path.join(DATA_PATH, 'aggregation.json')
        a_file = open(path)
        data_dict = json.load(a_file)
        self.dimension_data = data_dict["data"]
        self.dimensions = data_dict["dimensions"]
        self.dimension_keys = {}
        a_file.close()

        self.dimension_names = [name for name in self.dimensions.keys()]
        
        self.create_dimension_tables()
        self.create_fact()

        # Load the model
        model_path = os.path.join(DATA_PATH, 'fixtures_model.json')
        self.model = cubes.load_model(model_path)
        self.cube = self.model.cube("test")
        
    def create_dimension_tables(self):
        for dim, desc in self.dimensions.items():
            self.create_dimension(dim, desc, self.dimension_data[dim])

    def create_dimension(self, dim, desc, data):
        table = sqlalchemy.schema.Table(dim, self.metadata)

        fields = desc["attributes"]
        key = desc.get("key")
        if not key:
            key = fields[0]

        for field in fields:
            if isinstance(field,basestring):
                field = (field, "string")
            
            field_name = field[0]
            field_type = field[1]
            
            if field_type == "string":
                col_type = sqlalchemy.types.String
            elif field_type == "integer":
                col_type = sqlalchemy.types.Integer
            elif field_type == "float":
                col_type = sqlalchemy.types.Float
            else:
                raise Exception("Unknown field type: %s" % field_type)
                
            column = sqlalchemy.schema.Column(field_name, col_type)
            table.append_column(column)
            
        table.create(self.connection)
        
        for record in data:
            ins = table.insert(record)
            self.connection.execute(ins)
        
        table.metadata.reflect()
        
        key_col = table.c[key]
        sel = sqlalchemy.sql.select([key_col], from_obj = table)
        values = [result[key] for result in self.connection.execute(sel)]
        self.dimension_keys[dim] = values
    
    def create_fact(self):
        dimensions = [
                ["from", "entity"],
                ["to", "entity"],
                ["color", "color"],
                ["tone", "tone"],
                ["temp", "temp"],
                ["size", "size"]
            ]
            
        table = sqlalchemy.schema.Table("fact", self.metadata)

        table.append_column(sqlalchemy.schema.Column("id", sqlalchemy.types.Integer, 
                                                    sqlalchemy.schema.Sequence('fact_id_seq'),
                                                    primary_key = True))

        # Create columns for dimensions 
        for field, ignore in dimensions:
            column = sqlalchemy.schema.Column(field, sqlalchemy.types.String)
            table.append_column(column)
        
        # Create measures
        table.append_column(Column("amount", Float))
        table.append_column(Column("discount", Float))

        table.create(self.connection)

        self.metadata.reflect()

        # Make sure that we will get the same sequence each time
        random.seed(0) 

        for i in range(FACT_COUNT):
            record = {}
            for fact_field, dim_name in dimensions:
                key = random.choice(self.dimension_keys[dim_name])
                record[fact_field] = key

            ins = table.insert(record)
            self.connection.execute(ins)
        
    def test_model_valid(self):
        self.assertEqual(True, self.model.is_valid())

    def test_denormalize(self):
        # table = sqlalchemy.schema.Table("fact", self.metadata, autoload = True)
        view_name = "test_view"
        denormalizer = cubes.backends.sql.SQLDenormalizer(self.cube, self.connection)
        denormalizer.create_view(view_name)
        
        self.assertEqual(1, 1)
        browser = cubes.backends.sql.SQLBrowser(self.cube, connection = self.connection, 
                                                view_name = view_name)
        cell = browser.full_cube()
        result = browser.aggregate(cell)
        self.assertEqual(FACT_COUNT, result.summary["record_count"])
    
class SQLQueryTestCase(unittest.TestCase):
    def setUp(self):
        engine = sqlalchemy.create_engine('sqlite://')
        self.connection = engine.connect()
        self.metadata = sqlalchemy.MetaData()
        self.metadata.bind = engine
        
        self.table_name = "test"
        
        # Prepare table
        table = sqlalchemy.Table(self.table_name, self.metadata)
        table.append_column(Column("id", String))
        table.append_column(Column("color", String))
        table.append_column(Column("tone", String))
        table.append_column(Column("size", String))
        table.append_column(Column("temperature", String))
        table.create(self.connection)

        self.table = table

        # Prepare model
        self.model = cubes.Model()
        self.cube = cubes.Cube("test")
        self.model.add_cube(self.cube)

        dimension = cubes.Dimension("color", levels=["color", "tone"])
        self.cube.add_dimension(dimension)

        dimension = cubes.Dimension("size")
        self.cube.add_dimension(dimension)

    def test_query_column(self):
        full_cube = cubes.browser.Cell(self.cube)
        query = cubes.backends.sql.CubeQuery(full_cube, view=self.table)
        
        