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
logger.setLevel(logging.DEBUG)

class SQLTestCase(unittest.TestCase):
	
    def setUp(self):
        self.model = cubes.Model('test')
        
        date_desc = { "name": "date", 
                      "levels": { 
                                    "year": { 
                                        "key": "year", 
                                        "attributes": [
                                            {
                                                "name":"year",
                                                "order":"ascending"
                                            }
                                            ]
                                        }, 
                                    "month": {
                                        "key": "month", 
                                        "attributes": [
                                            {"name":"month", "order":"ascending"},
                                            {"name":"month_name"}] }
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
        
        self.cube.measures = [cubes.Attribute("amount")]
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
                    SELECT f.id AS "id",
                            f.amount AS "amount", 
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

        expected = ['id',
                    'amount',
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
        self.browser = cubes.backends.SQLBrowser(self.cube, connection = self.connection, 
                                                         view_name="view")
        self.full_cube = self.browser.full_cube()

    def test_fact_query(self):
        
        query = CubeQuery(self.full_cube, self.view)
        query.prepare()
        stmt = query.fact_statement(1)
        s = str(stmt)
        self.assertRegexpMatches(s, 'view\.id =')

        cuboid = self.full_cube.slice(self.date_dim, [2010])
        query = CubeQuery(cuboid, self.view)
        query.prepare()
        stmt = query.fact_statement(1)
        s = str(stmt)
        self.assertNotRegexpMatches(s, 'view\."date\.year" =')

    @unittest.skip("ordering facts not yet implemented")
    def test_natural_order(self):
        query = CubeQuery(self.full_cube, self.view)
        query.prepare()
        stmt = query.facts_statement
        s = str(stmt)
        self.assertRegexpMatches(s, 'ORDER BY')
        # self.assertRegexpMatches(s, 'ORDER BY.*date\.year')

    def test_fact_with_conditions(self):

        cuboid = self.full_cube.slice(self.date_dim, [2010])

        query = CubeQuery(cuboid, self.view)
        query.prepare()
        stmt = query.facts_statement
        s = str(stmt)
        self.assertRegexpMatches(s, 'WHERE')
        self.assertRegexpMatches(s, 'view\."date\.year" =')
        self.assertNotRegexpMatches(s, 'view\."date\.month" =')
        self.assertNotRegexpMatches(s, 'view\."class\.[^=]*"=')

        cuboid = self.full_cube.slice(self.date_dim, [2010, 4])
        query = CubeQuery(cuboid, self.view)
        query.prepare()
        stmt = query.facts_statement
        s = str(stmt)
        self.assertRegexpMatches(s, 'WHERE')
        self.assertRegexpMatches(s, r'view\."date\.year" =')
        self.assertRegexpMatches(s, r'view\."date\.month" =')

    def test_aggregate_full(self):
        query = CubeQuery(self.full_cube, self.view)
        query.prepare()
        stmt = query.summary_statement
        s = str(stmt)
        self.assertNotRegexpMatches(s, 'WHERE')
        self.assertRegexpMatches(s, r'sum(.*amount.*) AS amount_sum')
        self.execute(stmt)

    def test_aggregate_point(self):
        cuboid = self.full_cube.slice(self.date_dim, [2010])

        query = CubeQuery(cuboid, self.view)
        query.prepare()
        stmt = query.summary_statement
        s = str(stmt)
        s = re.sub(r'\n', ' ', s)
        self.assertRegexpMatches(s, r'WHERE')
        self.assertRegexpMatches(s, r'sum(.*amount.*) AS amount_sum')
        self.assertRegexpMatches(s, r'view\."date\.year" =')
        self.assertRegexpMatches(s, r'GROUP BY .*date\.year')
        self.assertNotRegexpMatches(s, r'GROUP BY .*date\.month')
        self.assertRegexpMatches(s, r'SELECT.*date\.year.*FROM')
        self.assertNotRegexpMatches(s, r'SELECT.*date\.month.*FROM')
        self.assertNotRegexpMatches(s, r'cls')
        self.execute(stmt)
        
        cuboid = self.full_cube.slice(self.date_dim, [2010, 4])

        query = CubeQuery(cuboid, self.view)
        query.prepare()
        stmt = query.summary_statement
        s = str(stmt)
        self.assertRegexpMatches(s, r'GROUP BY .*date\.year')
        self.assertRegexpMatches(s, r'GROUP BY .*date\.month')
        self.assertRegexpMatches(s, r'SELECT .*date\.year')
        self.assertRegexpMatches(s, r'SELECT.*date\.month')
        self.assertRegexpMatches(s, r'SELECT.*date\.month_name')
        self.assertNotRegexpMatches(s, r'cls')
        self.execute(stmt)
        
        cuboid = self.full_cube.slice(self.class_dim, [1])

        query = CubeQuery(cuboid, self.view)
        query.prepare()
        stmt = query.summary_statement
        s = str(stmt)
        self.assertRegexpMatches(s, r'cls')
        self.assertRegexpMatches(s, r'group_id')
        self.assertRegexpMatches(s, r'group_desc')
        self.assertNotRegexpMatches(s, r'class')
        self.execute(stmt)
        
    # @unittest.skip("not yet implemented")
    def test_next_drill_down(self):
        cuboid = self.full_cube

        query = CubeQuery(cuboid, self.view)
        query.drilldown = ["date"]
        query.prepare()
        stmt = query.drilldown_statement
        s = str(stmt)
        self.assertRegexpMatches(s, r'date\.year')
        self.assertNotRegexpMatches(s, r'date\.month')

        cuboid = self.full_cube.slice(self.date_dim, [2010])
        query = CubeQuery(cuboid, self.view)
        query.drilldown = ["date"]
        query.prepare()
        stmt = query.drilldown_statement
        s = str(stmt)
        self.assertRegexpMatches(s, r'date\.year')
        self.assertRegexpMatches(s, r'date\.month')

        cuboid = self.full_cube.slice(self.date_dim, [2010, 4])
        query = CubeQuery(cuboid, self.view)
        query.drilldown = ["date"]
        self.assertRaisesRegexp(ValueError, "Unable to drill-down.*last level", query.prepare)


    def test_explicit_drill_down(self):
        cuboid = self.full_cube
        query = CubeQuery(cuboid, self.view)
        query.drilldown = {"date": "year"}
        query.prepare()
        stmt = query.drilldown_statement
        s = str(stmt)
        self.assertRegexpMatches(s, r'date\.year')
        self.assertNotRegexpMatches(s, r'date\.month')

        cuboid = cuboid.slice("date", [2010])
        query = CubeQuery(cuboid, self.view)
        query.drilldown = {"date": "month"}
        query.prepare()
        stmt = query.drilldown_statement
        s = str(stmt)

        self.assertRegexpMatches(s, r'date\.year')
        self.assertRegexpMatches(s, r'date\.month')

    def execute(self, stmt):
        self.connection.execute(stmt)
        
if __name__ == '__main__':
    unittest.main()

