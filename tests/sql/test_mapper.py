import unittest
from cubes.sql.mapper import SnowflakeMapper
from cubes.model import *
from ..common import CubesTestCaseBase

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


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MapperTestCase))

    return suite
