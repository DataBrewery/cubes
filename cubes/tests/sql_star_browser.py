import unittest
import os
import json
import re
import cubes
import sqlalchemy
from sqlalchemy import Table, Column, Integer, Float, String, MetaData, ForeignKey
from sqlalchemy import create_engine

from cubes.backends.sql import StarBrowser, coalesce_physical

class StarSQLTestCase(unittest.TestCase):
    def setUp(self):
        model_desc = {
            "cubes": {
                "sales" : {
                    "measures": ["amount", "discount"],
                    "dimensions" : ["date", "flag", "product"],
                    "details": ["fact_detail1", "fact_detail2"],
                    "joins": [
                        {"master": "sales.date_id", "detail":"dim_date.id"},
                        {"master": "sales.product_id", "detail":"dim_product.id"},
                        {"master": "sales.category_id", "detail":"dim_category.id"}
                    ],
                    "mappings":{
                        "product.name": "dim_product.product_name",
                        "product.category": "dim_product.category_id",
                        "product.category_name.en": "dim_category.category_name_en",
                        "product.category_name.sk": "dim_category.category_name_sk",
                        "product.subcategory": "dim_category.subcategory_id",
                        "product.subcategory_name.en": "dim_category.subcategory_name_en",
                        "product.subcategory_name.sk": "dim_category.subcategory_name_sk"
                    }
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
                          "attributes": [ "id",
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
        
        table = Table('sales', metadata,
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
                        Column('product_name', String),
                    )

        table = Table('dim_category', metadata,
                        Column('id', Integer, primary_key=True),
                        Column('category_name_en', String),
                        Column('category_name_sk', String),
                        Column('subcategory_id', Integer),
                        Column('subcategory_name_en', String),
                        Column('subcategory_name_sk', String)
                    )

        metadata.create_all(engine)
        self.metadata = metadata

        self.model = cubes.Model(**model_desc)
        self.cube = self.model.cube("sales")
        self.browser = StarBrowser(self.cube,connection=self.connection, 
                                    dimension_prefix="dim_")
        self.cube.fact = 'sales'
        self.mapper = self.browser.mapper

class StarSQLAttributeMapperTestCase(StarSQLTestCase):
    def setUp(self):
        super(StarSQLAttributeMapperTestCase, self).setUp()
        self.mapper.mappings = { 
                    "product.name": "product.product_name",
                    "product.category": "product.category_id",
                    "subcategory.name.en": "subcategory.subcategory_name_en",
                    "subcategory.name.sk": "subcategory.subcategory_name_sk" 
                }
        
    def test_valid_model(self):
        """Model is valid"""
        self.assertEqual(True, self.model.is_valid())
        
    def test_logical_reference(self):

        attr = cubes.Attribute("month",dimension=self.model.dimension("date"))
        self.assertEqual("date.month", self.mapper.logical(attr))

        attr = cubes.Attribute("category",dimension=self.model.dimension("product"))
        self.assertEqual("product.category", self.mapper.logical(attr))

        attr = cubes.Attribute("flag",dimension=self.model.dimension("flag"))
        self.assertEqual("flag", self.mapper.logical(attr))

        attr = cubes.Attribute("measure",dimension=None)
        self.assertEqual("measure", self.mapper.logical(attr))

    def test_logical_reference_as_string(self):
        self.assertRaises(AttributeError, self.mapper.logical, "amount")

    def test_dont_simplify_dimension_references(self):
        self.mapper.simplify_dimension_references = False

        attr = cubes.Attribute("flag",dimension=self.model.dimension("flag"))
        self.assertEqual("flag.flag", self.mapper.logical(attr))

        attr = cubes.Attribute("measure",dimension=None)
        self.assertEqual("measure", self.mapper.logical(attr))

    def test_logical_split(self):
        split = self.mapper.split_logical
        
        self.assertEqual(('foo', 'bar'), split('foo.bar'))
        self.assertEqual(('foo', 'bar.baz'), split('foo.bar.baz'))
        self.assertEqual((None, 'foo'), split('foo'))
        
    def assertMapping(self, expected, logical_ref, locale = None):
        """Create string reference by concatentanig table and column name.
        No schema is expected (is ignored)."""
        
        attr = self.mapper.attributes[logical_ref]
        ref = self.mapper.physical(attr, locale)
        sref = ref[1] + "." + ref[2]
        self.assertEqual(expected, sref)

    def test_physical_refs_dimensions(self):
        """Testing correct default mappings of dimensions (with and without 
        explicit default prefix) in physical references."""

        # No dimension prefix
        self.mapper.dimension_table_prefix = None
        dim = self.model.dimension("product")
        self.assertMapping("date.year", "date.year")
        self.assertMapping("sales.flag", "flag")
        self.assertMapping("sales.amount", "amount")
        # self.assertEqual("fact.flag", sref("flag.flag"))

        # With prefix
        self.mapper.dimension_table_prefix = "dm_"
        self.assertMapping("dm_date.year", "date.year")
        self.assertMapping("dm_date.month_name", "date.month_name")
        self.assertMapping("sales.flag", "flag")
        self.assertMapping("sales.amount", "amount")
        self.mapper.dimension_table_prefix = None

    def test_coalesce_physical(self):
        def assertPhysical(expected, actual, default=None):
            ref = coalesce_physical(actual, default)
            self.assertEqual(expected, ref)
            
        assertPhysical((None, "table", "column"), "table.column")
        assertPhysical((None, "table", "column.foo"), "table.column.foo")
        assertPhysical((None, "table", "column"), ["table", "column"])
        assertPhysical(("schema", "table", "column"), ["schema","table", "column"])
        assertPhysical((None, "table", "column"), {"column":"column"}, "table")
        assertPhysical((None, "table", "column"), {"table":"table",
                                                        "column":"column"})
        assertPhysical(("schema", "table", "column"), {"schema":"schema",
                                                        "table":"table",
                                                        "column":"column"})

    def test_physical_refs_flat_dims(self):
        self.cube.fact = None
        self.assertMapping("sales.flag", "flag")

    def test_physical_refs_facts(self):
        """Testing correct mappings of fact attributes in physical references"""

        fact = self.cube.fact
        self.cube.fact = None
        self.assertMapping("sales.amount", "amount")
        # self.assertEqual("sales.flag", sref("flag.flag"))
        self.cube.fact = fact
        
    def test_physical_refs_with_mappings_and_locales(self):
        """Testing correct mappings of mapped attributes and localized 
        attributes in physical references"""

        # Test defaults
        self.assertMapping("dim_date.month_name", "date.month_name")
        self.assertMapping("dim_category.category_name_en", "product.category_name")
        self.assertMapping("dim_category.category_name_sk", "product.category_name", "sk")
        self.assertMapping("dim_category.category_name_en", "product.category_name", "de")

        # Test with mapping
        self.assertMapping("dim_product.product_name", "product.name")
        self.assertMapping("dim_product.category_id", "product.category")
        self.assertMapping("dim_product.product_name", "product.name", "sk")
        self.assertMapping("dim_category.subcategory_name_en", "product.subcategory_name")
        self.assertMapping("dim_category.subcategory_name_sk", "product.subcategory_name", "sk")
        self.assertMapping("dim_category.subcategory_name_en", "product.subcategory_name", "de")
                
class JoinsTestCase(StarSQLTestCase):
    def setUp(self):
        super(JoinsTestCase, self).setUp()
        
        self.joins = [
                {"master":"fact.date_id", "detail": "date.id"},
                {"master":["fact", "product_id"], "detail": "product.id"},
                {"master":"fact.contract_date_id", "detail": "date.id", "alias":"contract_date"},
                {"master":"product.subcategory_id", "detail": "subcategory.id"},
                {"master":"subcategory.category_id", "detail": "category.id"}
            ]
        self.mapper._collect_joins(self.joins)
        
    def test_basic_joins(self):
        relevant = self.mapper.relevant_joins([[None,"date"]])
        self.assertEqual(1, len(relevant))
        self.assertEqual("date", relevant[0].detail.table)
        self.assertEqual(None, relevant[0].alias)

        relevant = self.mapper.relevant_joins([[None,"product","name"]])
        self.assertEqual(1, len(relevant))
        self.assertEqual("product", relevant[0].detail.table)
        self.assertEqual(None, relevant[0].alias)

    def test_alias(self):
        relevant = self.mapper.relevant_joins([[None,"contract_date"]])
        self.assertEqual(1, len(relevant))
        self.assertEqual("date", relevant[0].detail.table)
        self.assertEqual("contract_date", relevant[0].alias)
        
    def test_snowflake(self):
        relevant = self.mapper.relevant_joins([[None,"subcategory"]])
        
        self.assertEqual(2, len(relevant))
        test = sorted([r.detail.table for r in relevant])
        self.assertEqual(["product","subcategory"], test)
        self.assertEqual([None, None], [r.alias for r in relevant])

        relevant = self.mapper.relevant_joins([[None,"category"]])
        
        self.assertEqual(3, len(relevant))
        test = sorted([r.detail.table for r in relevant])
        self.assertEqual(["category", "product","subcategory"], test)
        self.assertEqual([None, None, None], [r.alias for r in relevant])

class StarValidationTestCase(StarSQLTestCase):
    @unittest.skip("not implemented")
    def test_validate(self):
        result = self.browser.validate_model()
        self.assertEqual(0, len(result), 'message')
        
class StarSQLAggregationTestCase(StarSQLTestCase):
    def setUp(self):
        super(StarSQLAggregationTestCase, self).setUp()
        fact = {
            "id":1,
            "amount":100,
            "discount":20,
            "fact_detail1":"foo",
            "fact_detail2":"bar",
            "flag":1,
            "date_id":20120308,
            "product_id":1,
            "category_id":10
        }

        date = {
            "id": 20120308,
            "day": 8,
            "month": 3,
            "month_name": "March",
            "month_sname": "Mar",
            "year": 2012
        }

        product = {
            "id": 1,
            "category_id": 10,
            "product_name": "Cool Thing"
        }

        category = {
            "id": 10,
            "category_name_en": "Things",
            "category_name_sk": "Veci",
            "subcategory_id": 20,
            "subcategory_name_en": "Cool Things",
            "subcategory_name_sk": "Super Veci"
        }

        table = self.table("sales")
        self.connection.execute(table.insert(), fact)
        table = self.table("dim_date")
        self.connection.execute(table.insert(), date)
        table = self.table("dim_product")
        self.connection.execute(table.insert(), product)
        table = self.table("dim_category")
        self.connection.execute(table.insert(), category)

    def table(self, name):
        return sqlalchemy.Table(name, self.metadata,
                                autoload=True)
    
    # @unittest.skip("not implemented")
    def test_get_fact(self):
        """Get single fact"""
        fact = self.browser.fact(1)

        self.assertIsNotNone(fact)
        self.assertEqual(17, len(fact.keys()))

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
    suite.addTest(unittest.makeSuite(JoinsTestCase))
    suite.addTest(unittest.makeSuite(StarSQLAggregationTestCase))
    suite.addTest(unittest.makeSuite(StarValidationTestCase))

    return suite
