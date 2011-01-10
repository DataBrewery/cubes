import unittest
import os
import cubes
import cubes.tests
import json

class QueryGeneratorTestCase(unittest.TestCase):
	
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

        date_dim = cubes.Dimension("date", date_desc)

        self.cube = self.model.create_cube("testcube")
        self.cube.add_dimension(date_dim)
        
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
                             }
        self.cube.fact = "ft_contract"
        self.cube.joins = [
                            { "master": "ft_contracts.date_id", "detail": "dm_date.date_id"},
                            { "master": "ft_contracts.cls_id", "detail": "dm_cls.cls_id"}
                            ]
    def test_star(self):
        results = self.model.validate()
        #if results:
        #    print "\nVALIDATION: %s\n" % results
        self.assertEqual(True, self.model.is_valid(), 'Model is not valid (contains errors)')

        string = 'SELECT ft_contracts.amount AS "amount", dm_date.year AS "date.year", ' \
                    'dm_date.month AS "date.month", dm_date.month_name AS "date.month_name"\n'  \
                    'FROM ft_contract AS ft_contract\n' \
                    'JOIN dm_date AS dm_date ON (dm_date.date_id = ft_contracts.date_id)\n' \
                    'JOIN dm_cls AS dm_cls ON (dm_cls.cls_id = ft_contracts.cls_id)'
            
        stmt = cubes.cube_select_statement(self.cube)
        # print "\nSELECT1: %s" % stmt
        # print "\nSELECT2: %s" % string

        self.assertEqual(string, stmt, 'Expected SELECT statement is not equal')
		
if __name__ == '__main__':
    unittest.main()

