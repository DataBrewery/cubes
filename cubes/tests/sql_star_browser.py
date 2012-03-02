import unittest
import os
import json
import re
import cubes
import sqlalchemy
from sqlalchemy import Table, Column, Integer, Float, String, MetaData, ForeignKey
from sqlalchemy import create_engine

from cubes.backends.sql import StarBrowser

class StarSQLTestCase(unittest.TestCase):
    def setUp(self):
        model_desc = {
            "cubes": {
                "star" : {
                    "measures": ["amount", "discount"],
                    "dimensions" : ["date", "flag", "product"],
                    "details": ["fact_detail1", "fact_detail2"]
                }
            },
            "dimensions" :
            [
                {
                    "name": "date",
                    "levels": [
                        { "name": "year", "attributes": ["year"] },
                        { "name": "month", "attributes":  ["month", "month_name", "month_sname"] },
                        { "name": "day", "attributes": ["id", "day"] }
                    ],
                    "hierarchy": ["year", "month", "day"]
                },
                { "name": "flag" },
                { "name": "product", "attributes": ["category", "subcategory"] }
            ]
        }       
        self.model = cubes.Model(**model_desc)
        self.cube = self.model.cube("star")
        # self.query = StarQuery(self.cube)

        engine = sqlalchemy.create_engine('sqlite://')
        self.connection = engine.connect()
        metadata = sqlalchemy.MetaData()
        metadata.bind = engine
        
        table = Table('fact', metadata,
                        Column('id', Integer, primary_key=True),
                        Column('amount', Float),
                        Column('discount', Float),
                        Column('fact_detail1', String),
                        Column('fact_detail2', String),
                        Column('flag', String),
                        Column('date_id', Integer),
                        Column('product_id', Integer),
                        Column('category_id', Integer)
                    )

        table = Table('dim_date', metadata,
                        Column('id', Integer, primary_key=True),
                        Column('day', Integer),
                        Column('month', Integer),
                        Column('month_name', String),
                        Column('month_sname', String),
                        Column('year', Integer)
                    )
                    
        table = Table('dim_product', metadata,
                        Column('id', Integer, primary_key=True),
                        Column('category_id', Integer),
                        Column('product_name', String)
                    )

        table = Table('dim_category', metadata,
                        Column('id', Integer, primary_key=True),
                        Column('category_name', String),
                    )

        metadata.create_all(engine)
        self.metadata = metadata
        
    def test_valid_model(self):
        self.assertEqual(True, self.model.is_valid())
        
    @unittest.skip("not implemented")
    def test_aggregate_measure_only(self):
        """Aggregation result should: SELECT from fact only"""
        pass

    @unittest.skip("not implemented")
    def test_aggregate_flat_dimension(self):
        """Aggregation result should SELECT from fact table onle, group by flat dimension attribute"""
        pass

    @unittest.skip("not implemented")
    def test_aggregate_joins(self):
        """Aggregation result should:
            * join date only - no other dimension joined
            * join all dimensions
            * snowflake join
        """
        pass

    @unittest.skip("not implemented")
    def test_aggregate_details(self):
        """Aggregation result should:
            details should be added after aggregation
            * fact details
            * dimension details
        """
        pass

    @unittest.skip("not implemented")
    def test_aggregate_join_date(self):
        """Aggregation result should join only date, no other joins should be performed"""
        pass


    # def test_measure_selection(self):
        
def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(StarSQLTestCase))
    return suite
