import unittest
import cubes


class MapperTestCase(unittest.TestCase):
    def setUp(self):
        model_desc = {
            "cubes": [
                {
                    "name": "sales",
                    "measures": [
                            {"name":"amount", "aggregations":["sum", "min"]},
                            "discount"
                            ],
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
            ],
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
                        {"name": "category",
                            "attributes": ["category",
                                          {"name": "category_name", "locales": ["en", "sk"] }
                                          ]
                        },
                        {"name": "subcategory",
                            "attributes": ["subcategory",
                                            {"name": "subcategory_name", "locales": ["en", "sk"] }
                                        ]
                        },
                        { "name": "product",
                          "attributes": [ "id",
                                          {"name": "name"}
                                        ],
                        }
                    ]
                }
            ]
        }

        self.model = cubes.create_model(model_desc)
        self.cube = self.model.cube("sales")
        self.mapper = cubes.SnowflakeMapper(self.cube,dimension_prefix='dim_')

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

        self.assertEqual(True, self.mapper.simplify_dimension_references)
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
        self.mapper.dimension_prefix = None
        dim = self.model.dimension("product")
        self.assertMapping("date.year", "date.year")
        self.assertMapping("sales.flag", "flag")
        self.assertMapping("sales.amount", "amount")
        # self.assertEqual("fact.flag", sref("flag.flag"))

        # With prefix
        self.mapper.dimension_prefix = "dm_"
        self.assertMapping("dm_date.year", "date.year")
        self.assertMapping("dm_date.month_name", "date.month_name")
        self.assertMapping("sales.flag", "flag")
        self.assertMapping("sales.amount", "amount")
        self.mapper.dimension_prefix = None

    def test_coalesce_physical(self):
        def assertPhysical(expected, actual, default=None):
            ref = cubes.coalesce_physical(actual, default)
            self.assertEqual(expected, ref)

        assertPhysical((None, "table", "column", None), "table.column")
        assertPhysical((None, "table", "column.foo", None), "table.column.foo")
        assertPhysical((None, "table", "column", None), ["table", "column"])
        assertPhysical(("schema", "table", "column", None), ["schema","table", "column"])
        assertPhysical((None, "table", "column", None), {"column":"column"}, "table")
        assertPhysical((None, "table", "column", None), {"table":"table",
                                                        "column":"column"})
        assertPhysical(("schema", "table", "column", None), {"schema":"schema",
                                                        "table":"table",
                                                        "column":"column"})
        assertPhysical(("schema", "table", "column", "day"), {"schema":"schema",
                                                        "table":"table",
                                                        "column":"column",
                                                        "extract":"day"})

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


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MapperTestCase))

    return suite
