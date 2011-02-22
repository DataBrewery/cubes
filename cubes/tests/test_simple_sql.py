import unittest
import os
import cubes
import cubes.tests
import json
import re
import logging
from cubes.backends.sql.browser import CubeQuery
from sqlalchemy import Table, Column, Integer, Float, String, MetaData, ForeignKey
from sqlalchemy import create_engine

logger = logging.getLogger(cubes.default_logger_name())
logger.setLevel(logging.WARN)

class SQLTestCase(unittest.TestCase):
	
    def setUp(self):
        self.model = cubes.Model('test')
        
        date_desc = { "name": "date", 
                      "levels": { 
                                    "year": { "key": "year", "attributes": ["year"] }, 
                                    "month": { "key": "month", "attributes": ["month", "month_name"] }
                                } , 
                       "default_hierarchy": "ym",
                       "hierarchies": { 
                                "ym": { 
                                    "levels": ["year", "month"]
                                } 
                        }
                    }

        class_desc = { "name": "cls", 
                      "levels": { 
                                    "group": { "key": "group_id", "attributes": ["group_id", "group_desc"] }, 
                                    "class": { "key": "class_id", "attributes": ["class_id", "class_desc"] }
                                } , 
                       "default_hierarchy": "default",
                       "hierarchies": { 
                                "default": { 
                                    "levels": ["group", "class"]
                                } 
                        }
                    }

        self.cube = self.model.create_cube("testcube")

        self.date_dim = cubes.Dimension("date", date_desc)
        self.cube.add_dimension(self.date_dim)
        self.class_dim = cubes.Dimension("cls", class_desc)
        self.cube.add_dimension(self.class_dim)
        
        self.cube.measures = ["amount"]
        self.cube.mappings = {
                                "amount": "ft_contracts.amount",
                                "date.year": "dm_date.year",
                                "date.month": "dm_date.month",
                                "date.month_name": "dm_date.month_name",
                                "cls.group_id": "dm_cls.group_id",
                                "cls.class_id": "dm_cls.class_id",
                                "cls.group_desc": "dm_cls.group_desc",
                                "cls.class_desc": "dm_cls.class_desc",
                                "cls.id": "dm_cls.id",
                                "date.id": "dm_date.id",
                                "fact.date_id": "ft_contracts.date_id",
                                "fact.cls_id": "ft_contracts.cls_id"
                             }
        self.cube.fact = "ft_contracts"
        self.mappings2 = {
                              "amount": "ft_contracts.amount"
                           }
        self.cube.joins = [
                            { "master": "fact.date_id", "detail": "date.id"},
                            { "master": "fact.cls_id", "detail": "cls.id"}
                            ]

        self.prepare_data()
        
    def prepare_data(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.connection = self.engine.connect()
        
        self.metadata = MetaData()
        self.view = Table('view', self.metadata,
            Column("id", Integer, primary_key=True),
            Column("amount", Float),
            Column("date.year", Integer),
            Column("date.month", Integer),
            Column("date.month_name", String),
            Column("cls.group_id", Integer),
            Column("cls.group_desc", String),
            Column("cls.class_id", Integer),
            Column("cls.class_desc", String)
        )
        self.metadata.create_all(self.engine)
        ins = self.view.insert()
        
    def assertStatementEqual(self, first, second):
        str1 = re.sub(r"[ \n\t]+", " ", first.strip())
        str2 = re.sub(r"[ \n\t]+", " ", second.strip())
        r = r"((AS )d[0-9]+)|(d[0-9]+\.)"
        str1 = re.sub(r, "@", str1)
        str2 = re.sub(r, "@", str2)
        self.assertEqual(str1, str2)

class SQLBuiderTestCase(SQLTestCase):

    def setUp(self):
        super(SQLBuiderTestCase, self).setUp()
        
        self.builder = cubes.backends.SimpleSQLBuilder(self.cube, connection = None)
        self.stmt_expexted = '''
                    SELECT f.amount AS "amount", 
                            d1.year AS "date.year", 
                            d1.month AS "date.month", 
                            d1.month_name AS "date.month_name", 
                            d2.group_id AS "cls.group_id", 
                            d2.group_desc AS "cls.group_desc", 
                            d2.class_id AS "cls.class_id", 
                            d2.class_desc AS "cls.class_desc" 
                    FROM ft_contracts AS f 
                    JOIN dm_date AS d1 ON (d1.id = f.date_id) 
                    JOIN dm_cls AS d2 ON (d2.id = f.cls_id)
                    '''

    def test_build(self):
        results = self.model.validate()

        self.assertEqual(True, self.model.is_valid(), 'Model is not valid (contains errors)')

        self.builder.create_select_statement()
        
        fields = self.builder.selected_fields

        expected = ['amount',
                    'date.year',
                    'date.month',
                    'date.month_name',
                    'cls.group_id',
                    'cls.group_desc',
                    'cls.class_id',
                    'cls.class_desc']

        self.assertEqual(fields, expected)
            
        stmt = self.builder.select_statement
        self.assertStatementEqual(stmt, self.stmt_expexted)
        
    def test_default_dims(self):
        self.cube.mappings = self.mappings2
        self.builder.dimension_table_prefix = "dm_"

        self.builder.create_select_statement()
        stmt = self.builder.select_statement
        self.assertStatementEqual(stmt, self.stmt_expexted)
        
class SQLBrowserTestCase(SQLTestCase):

    def setUp(self):
        super(SQLBrowserTestCase, self).setUp()
        self.browser = cubes.backends.SimpleSQLBrowser(self.cube, connection = self.connection, 
                                                         view_name="view")
        self.full_cube = self.browser.full_cube()

    def test_fact_query(self):
        
        query = CubeQuery(self.full_cube, self.view)
        stmt = query.fact_statement(1)
        self.assertRegexpMatches(stmt, 'view\.id =')

    def test_fact_with_conditions(self):

        cuboid = self.full_cube.slice(self.date_dim, [2010])

        query = CubeQuery(cuboid, self.view)
        stmt = query.fact_statement(1)

        cuboid = self.full_cube.slice(self.date_dim, [2010, 4])
        query = CubeQuery(cuboid, self.view)
        stmt = query.fact_statement(1)
        self.assertRegexpMatches(stmt, 'WHERE')
        self.assertRegexpMatches(stmt, 'view\."date\.year" =')
        self.assertRegexpMatches(stmt, 'view\."date\.month" =')


if __name__ == '__main__':
    unittest.main()

