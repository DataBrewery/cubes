import unittest
import os
import cubes
import cubes.tests
import json
import re
import logging

logger = logging.getLogger(cubes.default_logger_name())
logger.setLevel(logging.WARN)

class SimpleSQLTestCase(unittest.TestCase):
	
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

        dim = cubes.Dimension("date", date_desc)
        self.cube.add_dimension(dim)
        dim = cubes.Dimension("cls", class_desc)
        self.cube.add_dimension(dim)
        
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

    def assertStatementEqual(self, first, second):
        str1 = re.sub(r"[ \n\t]+", " ", first.strip())
        str2 = re.sub(r"[ \n\t]+", " ", second.strip())
        r = r"((AS )d[0-9]+)|(d[0-9]+\.)"
        str1 = re.sub(r, "@", str1)
        str2 = re.sub(r, "@", str2)
        self.assertEqual(str1, str2)
    
if __name__ == '__main__':
    unittest.main()

