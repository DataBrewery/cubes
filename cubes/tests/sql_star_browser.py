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
            "dimensions" : [
                {
                    "name": "date",
                    "levels": [
                        { "name": "year", "attributes": ["year"] },
                        { "name": "month", "attributes": 
                                    ["month", "month_name", "month_sname"] },
                        { "name": "day", "attributes": ["id", "day"] }
                    ],
                    "hierarchy": ["year", "month", "day"]
                },
                { "name": "flag" },
                { "name": "product", 
                    "levels": [
                        { "name": "product", 
                          "attributes": [ "product",
                                          {"name": "name"}
                                        ],
                        },
                        {"name": "category",
                            "attributes": ["category",
                                          {"name": "category_name", "locales": ["en", "sk"] }
                                          ]
                        },
                        {"name": "subcategory",
                            "attributes": ["subcategory",
                                            {"name": "subcategory_name", "locales": ["en", "sk"] }
                                        ]
                        }
                    ]
                }
            ]
        }       
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

        self.model = cubes.Model(**model_desc)
        self.cube = self.model.cube("star")
        self.browser = StarBrowser(self.cube)
        self.cube.fact = 'fact'
        self.mapper = self.browser.mapper

class StarSQLAttributeMapperTestCase(StarSQLTestCase):
    def setUp(self):
        super(StarSQLAttributeMapperTestCase, self).setUp()
        self.mapper.mappings = { 
                    "product.name": "product.product_name",
                    "subcategory.name.en": "subcategory.subcategory_name_en",
                    "subcategory.name.sk": "subcategory.subcategory_name_sk" 
                }
        
    def test_valid_model(self):
        """Model is valid"""
        self.assertEqual(True, self.model.is_valid())
        
    def test_logical_reference(self):

        dim = self.model.dimension("date")
        attr = "month"
        self.assertEqual("date.month", self.mapper.logical(dim, attr))

        dim = self.model.dimension("product")
        attr = "category"
        self.assertEqual("product.category", self.mapper.logical(dim, attr))

        dim = self.model.dimension("flag")
        attr = "flag"
        self.assertEqual("flag", self.mapper.logical(dim, attr))

        attr = "anything"
        self.assertEqual("flag", self.mapper.logical(dim, attr))

        self.assertEqual("amount", self.mapper.logical(None, "amount"))

    def test_dont_simplify_dimension_references(self):
        self.mapper.simplify_dimension_references = False

        dim = self.model.dimension("flag")
        attr = "flag"
        self.assertEqual("flag.flag", self.mapper.logical(dim, attr))

        attr = "anything"
        self.assertEqual("flag.anything", self.mapper.logical(dim, attr))

    def test_logical_split(self):
        split = self.mapper.split_logical
        
        self.assertEqual(('foo', 'bar'), split('foo.bar'))
        self.assertEqual(('foo', 'bar.baz'), split('foo.bar.baz'))
        self.assertEqual((None, 'foo'), split('foo'))
        
    def assertMapping(self, expected, logical_ref, locale = None):
        """Create string reference by concatentanig table and column name"""
        (dim, attr) = self.mapper.attributes[logical_ref]
        ref = self.mapper.physical(dim, attr, locale)
        sref = ref[0] + "." + ref[1]
        self.assertEqual(expected, sref)

    def test_physical_refs_dimensions(self):
        """Testing correct default mappings of dimensions (with and without 
        explicit default prefix) in physical references."""

        # No dimension prefix
        dim = self.model.dimension("product")
        self.assertMapping("date.year", "date.year")
        self.assertMapping("fact.flag", "flag")
        self.assertMapping("fact.amount", "amount")
        # self.assertEqual("fact.flag", sref("flag.flag"))

        # With prefix
        self.mapper.dimension_table_prefix = "dm_"
        self.assertMapping("dm_date.year", "date.year")
        self.assertMapping("dm_date.month_name", "date.month_name")
        self.assertMapping("fact.flag", "flag")
        self.assertMapping("fact.amount", "amount")
        self.mapper.dimension_table_prefix = None

    def test_physical_refs_flat_dims(self):
        self.cube.fact = None
        self.assertMapping("star.flag", "flag")

    def test_physical_refs_facts(self):
        """Testing correct mappings of fact attributes in physical references"""

        fact = self.cube.fact
        self.cube.fact = None
        self.assertMapping("star.amount", "amount")
        # self.assertEqual("star.flag", sref("flag.flag"))
        self.cube.fact = fact
        
    def test_physical_refs_with_mappings_and_locales(self):
        """Testing correct mappings of mapped attributes and localized 
        attributes in physical references"""

        # Test defaults
        self.assertMapping("date.month_name", "date.month_name")
        self.assertMapping("product.category_name_en", "product.category_name")
        self.assertMapping("product.category_name_sk", "product.category_name", "sk")
        self.assertMapping("product.category_name_en", "product.category_name", "de")

        # Test with mapping
        self.assertMapping("product.name", "product.name")
        self.assertMapping("product.name", "product.name", "sk")
        self.assertMapping("product.subcategory_name_en", "product.subcategory_name")
        self.assertMapping("product.subcategory_name_sk", "product.subcategory_name", "sk")
        self.assertMapping("product.subcategory_name_en", "product.subcategory_name", "de")
        
class StarSQLAggregationTestCase(StarSQLTestCase):

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
    suite.addTest(unittest.makeSuite(StarSQLAttributeMapperTestCase))
    suite.addTest(unittest.makeSuite(StarSQLAggregationTestCase))
    return suite
