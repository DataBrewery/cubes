import unittest
from cubes.sql.mapper import SnowflakeMapper
from cubes.model import Cube
from ..common import CubesTestCaseBase
from cubes.sql.mapper import Naming

class MapperTestCase(CubesTestCaseBase):
    def setUp(self):
        super(MapperTestCase, self).setUp()

        self.modelmd = self.model_metadata("mapper_test.json")
        self.workspace = self.create_workspace(model=self.modelmd)

        self.cube = self.workspace.cube("sales")
        self.mapper = SnowflakeMapper(self.cube, dimension_prefix='dim_', dimension_suffix="_dim")

        self.mapper.mappings = {
            "product.name": "product.product_name",
            "product.category": "product.category_id",
            "subcategory.name.en": "subcategory.subcategory_name_en",
            "subcategory.name.sk": "subcategory.subcategory_name_sk"
        }

    def test_logical_reference(self):

        dim = self.workspace.dimension("date")
        attr = Attribute("month", dimension=dim)
        self.assertEqual("date.month", self.mapper.logical(attr))

        attr = Attribute("month", dimension=dim)
        dim = self.workspace.dimension("product")
        attr = Attribute("category", dimension=dim)
        self.assertEqual("product.category", self.mapper.logical(attr))

        self.assertEqual(True, self.mapper.simplify_dimension_references)
        dim = self.workspace.dimension("flag")
        attr = Attribute("flag", dimension=dim)
        self.assertEqual("flag", self.mapper.logical(attr))

        attr = Attribute("measure", dimension=None)
        self.assertEqual("measure", self.mapper.logical(attr))

    def test_logical_reference_as_string(self):
        self.assertRaises(AttributeError, self.mapper.logical, "amount")

    def test_dont_simplify_dimension_references(self):
        self.mapper.simplify_dimension_references = False

        dim = self.workspace.dimension("flag")
        attr = Attribute("flag", dimension=dim)
        self.assertEqual("flag.flag", self.mapper.logical(attr))

        attr = Attribute("measure", dimension=None)
        self.assertEqual("measure", self.mapper.logical(attr))

    def test_logical_split(self):
        split = self.mapper.split_logical

        self.assertEqual(('foo', 'bar'), split('foo.bar'))
        self.assertEqual(('foo', 'bar.baz'), split('foo.bar.baz'))
        self.assertEqual((None, 'foo'), split('foo'))

    def assertMapping(self, expected, logical_ref, locale=None):
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
        self.mapper.dimension_prefix = ""
        self.mapper.dimension_suffix = ""
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
        self.mapper.dimension_prefix = ""
        self.mapper.dimension_suffix = ""

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
        self.assertMapping("dim_date_dim.month_name", "date.month_name")
        self.assertMapping("dim_category_dim.category_name_en",
                           "product.category_name")
        self.assertMapping("dim_category_dim.category_name_sk",
                           "product.category_name", "sk")
        self.assertMapping("dim_category_dim.category_name_en",
                           "product.category_name", "de")

        # Test with mapping
        self.assertMapping("dim_product_dim.product_name", "product.name")
        self.assertMapping("dim_product_dim.category_id", "product.category")
        self.assertMapping("dim_product_dim.product_name", "product.name", "sk")
        self.assertMapping("dim_category_dim.subcategory_name_en",
                           "product.subcategory_name")
        self.assertMapping("dim_category_dim.subcategory_name_sk",
                           "product.subcategory_name", "sk")
        self.assertMapping("dim_category_dim.subcategory_name_en",
                           "product.subcategory_name", "de")


class NamingTestCase(unittest.TestCase):
    def test_dim_table_name(self):
        naming = Naming()
        self.assertEqual("date", naming.dimension_table_name("date"))

        naming = Naming({"dimension_prefix": "dim_"})
        self.assertEqual("dim_date", naming.dimension_table_name("date"))

        naming = Naming({"dimension_suffix": "_dim"})
        self.assertEqual("date_dim", naming.dimension_table_name("date"))

        naming = Naming({"dimension_prefix": "v_", "dimension_suffix": "_dim"})
        self.assertEqual("v_date_dim", naming.dimension_table_name("date"))

    def test_fact_table_name(self):
        naming = Naming()
        self.assertEqual("fact", naming.fact_table_name("fact"))

        naming = Naming({"fact_prefix": "ft_"})
        self.assertEqual("ft_fact", naming.fact_table_name("fact"))

        naming = Naming({"fact_suffix": "_ft"})
        self.assertEqual("fact_ft", naming.fact_table_name("fact"))

        naming = Naming({"fact_prefix": "v_", "fact_suffix": "_ft"})
        self.assertEqual("v_fact_ft", naming.fact_table_name("fact"))

    def test_dim_primary_key_name(self):
        naming = Naming()
        self.assertEqual("id", naming.dimension_primary_key("date"))

        naming = Naming({"dimension_key_prefix": "dw_",
                         "dimension_key_suffix": "_key"})
        self.assertEqual("id", naming.dimension_primary_key("date"))

        naming = Naming({"dimension_key_prefix": "key_",
                         "explicit_dimension_primary": True})
        self.assertEqual("key_date", naming.dimension_primary_key("date"))

        naming = Naming({"dimension_key_suffix": "_key",
                         "explicit_dimension_primary": True})
        self.assertEqual("date_key", naming.dimension_primary_key("date"))

        naming = Naming({"dimension_key_prefix": "dw_",
                         "dimension_key_suffix": "_key",
                         "explicit_dimension_primary": True})
        self.assertEqual("dw_date_key", naming.dimension_primary_key("date"))

    def test_dimension_keys(self):
        naming = Naming()
        self.assertCountEqual(naming.dimension_keys(["date", "country"]),
                              [("date", "date"), ("country", "country")])

        keys = ["id", "date_key", "key_date", "dw_date_id", "amount"]

        naming = Naming({"dimension_key_prefix": "key_"})

        self.assertCountEqual(naming.dimension_keys(keys),
                             [("key_date", "date")])

        naming = Naming({"dimension_key_suffix": "_key"})
        self.assertCountEqual(naming.dimension_keys(keys),
                              [("date_key", "date")])


        naming = Naming({"dimension_key_prefix": "dw_",
                         "dimension_key_suffix": "_id"})
        self.assertCountEqual(naming.dimension_keys(keys),
                              [("dw_date_id", "date")])

    def test_dimensions(self):
        names = ["fact_sales", "dim_date", "date_dim", "v_date_dm", "other"]

        naming = Naming()
        self.assertCountEqual(naming.dimensions(["date", "customer"]),
                              [("date", "date"), ("customer", "customer")])

        naming = Naming({"dimension_prefix": "dim_"})
        self.assertEqual(naming.dimensions(names),
                        [("dim_date", "date")])

        naming = Naming({"dimension_suffix": "_dim"})
        self.assertEqual(naming.dimensions(names),
                        [("date_dim", "date")])

        naming = Naming({"dimension_prefix": "v_", "dimension_suffix": "_dm"})
        self.assertEqual(naming.dimensions(names),
                        [("v_date_dm", "date")])

    def test_facts(self):
        names = ["dim_date", "fact_sales", "sales_fact", "v_sales_ft", "other"]

        naming = Naming()
        self.assertCountEqual(naming.facts(["sales", "events"]),
                              [("sales", "sales"), ("events", "events")])

        naming = Naming({"fact_prefix": "fact_"})
        self.assertEqual(naming.facts(names),
                        [("fact_sales", "sales")])

        naming = Naming({"fact_suffix": "_fact"})
        self.assertEqual(naming.facts(names),
                        [("sales_fact", "sales")])

        naming = Naming({"fact_prefix": "v_", "fact_suffix": "_ft"})
        self.assertEqual(naming.facts(names),
                        [("v_sales_ft", "sales")])

