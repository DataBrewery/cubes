import unittest
import os
import json
import re
import cubes
from cubes.errors import *

from common import DATA_PATH

DIM_DATE_DESC = { 
            "name": "date",
            "levels": [
                    {"name":"year"},
                    {"name":"month", "attributes":["month", "month_name"]},
                    {"name":"day"}
                ],
            "hierarchies": [
                { "name": "ymd", "levels": ["year", "month", "day"] },
                { "name": "ymd", "levels": ["year", "month"] },
            ]
       }

DIM_FLAG_DESC = { "name": "flag" }

DIM_PRODUCT_DESC = { 
            "name": "product",
            "levels": [
                {"name":"category", "attributes":["key", "name"]},
                {"name":"subcategory", "attributes":["key", "name"]},
                {"name":"product", "attributes":["key", "name", "description"]}
            ]
        }


class AttributeTestCase(unittest.TestCase):
    """docstring for AttributeTestCase"""
    def test_basics(self):
        """Attribute creation and attribute references"""
        attr = cubes.Attribute("foo")
        self.assertEqual("foo", attr.name)
        self.assertEqual("foo", str(attr))
        self.assertEqual("foo", attr.ref())
        self.assertEqual("foo", attr.ref(simplify=False))
        self.assertEqual("foo", attr.ref(simplify=True))

    def test_locale(self):
        """References to localizable attributes"""

        attr = cubes.Attribute("foo")
        self.assertRaises(ArgumentError, attr.ref, locale="xx")

        attr = cubes.Attribute("foo", locales=["en", "sk"])
        self.assertEqual("foo", attr.name)
        self.assertEqual("foo", str(attr))
        self.assertEqual("foo", attr.ref())
        self.assertEqual("foo.en", attr.ref(locale="en"))
        self.assertEqual("foo.sk", attr.ref(locale="sk"))
        self.assertRaises(ArgumentError, attr.ref, locale="xx")

    def test_simplify(self):
        """Simplification of attribute reference (with and without details)"""

        level = cubes.Level("name", attributes=["name"])
        dim = cubes.Dimension("group", levels=[level])
        attr = dim.attribute("name")
        self.assertEqual("name", attr.name)
        self.assertEqual("name", str(attr))
        self.assertEqual("group", attr.ref())
        self.assertEqual("group.name", attr.ref(simplify=False))
        self.assertEqual("group", attr.ref(simplify=True))

        level = cubes.Level("name", attributes=["key", "name"])
        dim = cubes.Dimension("group", levels=[level])
        attr = dim.attribute("name")
        self.assertEqual("name", attr.name)
        self.assertEqual("name", str(attr))
        self.assertEqual("group.name", attr.ref())
        self.assertEqual("group.name", attr.ref(simplify=False))
        self.assertEqual("group.name", attr.ref(simplify=True))

    def test_coalesce_attribute(self):
        """Coalesce attribute object (string or Attribute instance)"""

        level = cubes.Level("name", attributes=["key", "name"])
        dim = cubes.Dimension("group", levels=[level])

        obj = cubes.coalesce_attribute("name")
        self.assertIsInstance(obj, cubes.Attribute)
        self.assertEqual("name", obj.name)

        obj = cubes.coalesce_attribute({"name":"key"}, dim)
        self.assertIsInstance(obj, cubes.Attribute)
        self.assertEqual("key", obj.name)
        self.assertEqual(dim, obj.dimension)

        attr = dim.attribute("key")
        obj = cubes.coalesce_attribute(attr)
        self.assertIsInstance(obj, cubes.Attribute)
        self.assertEqual("key", obj.name)
        self.assertEqual(obj, attr)

    def test_attribute_list(self):
        """Create attribute list from strings or Attribute instances"""
        self.assertEqual([], cubes.attribute_list([]))

        names = ["name", "key"]
        attrs = cubes.attribute_list(names)

        for name, attr in zip(names, attrs):
            self.assertIsInstance(attr, cubes.Attribute)
            self.assertEqual(name, attr.name)

class LevelTestCase(unittest.TestCase):
    """docstring for LevelTestCase"""
    def test_initialization(self):
        """Empty attribute list for new level should raise an exception """
        self.assertRaises(ModelError, cubes.Level, "month", [])

    def test_has_details(self):
        """Level "has_details" flag"""
        attrs = cubes.attribute_list(["year"])
        level = cubes.Level("year", attrs)
        self.assertFalse(level.has_details)

        attrs = cubes.attribute_list(["month", "month_name"])
        level = cubes.Level("month", attrs)
        self.assertTrue(level.has_details)

    def test_operators(self):
        """Level to string conversion"""
        self.assertEqual("date", str(cubes.Level("date", ["foo"])))

    def test_create(self):
        """Create level from a dictionary"""
        desc = "year"
        level = cubes.create_level(desc)
        self.assertIsInstance(level, cubes.Level)
        self.assertEqual("year", level.name)
        self.assertEqual(["year"], [str(a) for a in level.attributes])

        # Test default: Attributes
        desc = {"name":"year"}
        level = cubes.create_level(desc)
        self.assertIsInstance(level, cubes.Level)
        self.assertEqual("year", level.name)
        self.assertEqual(["year"], [str(a) for a in level.attributes])

        # Test default: Attributes
        desc = { "name":"year", "attributes":["key"] }
        level = cubes.create_level(desc)
        self.assertIsInstance(level, cubes.Level)
        self.assertEqual("year", level.name)
        self.assertEqual(["key"], [str(a) for a in level.attributes])
        self.assertFalse(level.has_details)

        desc = { "name":"year", "attributes":["key", "label"] }
        level = cubes.create_level(desc)
        self.assertTrue(level.has_details)
        self.assertEqual(["key", "label"], [str(a) for a in level.attributes])

        # Level from description with full details
        desc = {
                    "name": "month",
                    "attributes": [
                        { "name":"month" },
                        { "name":"month_name", "locales":["en", "sk"] },
                        { "name":"month_sname", "locales":["en", "sk"] }
                    ]
                }
        level = cubes.create_level(desc)
        self.assertTrue(level.has_details)
        self.assertEqual(3, len(level.attributes))
        names = [str(a) for a in level.attributes]
        self.assertEqual(["month", "month_name", "month_sname"], names)

    def test_key_label_attributes(self):
        """Test key and label attributes - explicit and implicit"""

        attrs = cubes.attribute_list(["code"])
        level = cubes.Level("product", attrs)
        self.assertIsInstance(level.key, cubes.Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, cubes.Attribute)
        self.assertEqual("code", str(level.label_attribute))

        attrs = cubes.attribute_list(["code", "name"])
        level = cubes.Level("product", attrs)
        self.assertIsInstance(level.key, cubes.Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, cubes.Attribute)
        self.assertEqual("name", str(level.label_attribute))

        attrs = cubes.attribute_list(["info", "code", "name"])
        level = cubes.Level("product", attrs, key="code", label_attribute="name")
        self.assertIsInstance(level.key, cubes.Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, cubes.Attribute)
        self.assertEqual("name", str(level.label_attribute))

        # Test key/label in full desc
        desc = {
                    "name": "product",
                    "attributes": ["info", "code", "name"],
                    "label_attribute": "name",
                    "key": "code"
                }
        level = cubes.create_level(desc)
        self.assertIsInstance(level.key, cubes.Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, cubes.Attribute)
        self.assertEqual("name", str(level.label_attribute))

    def test_comparison(self):
        """Comparison of level instances"""

        attrs = cubes.attribute_list(["info", "code", "name"])
        level1 = cubes.Level("product", attrs, key="code", label_attribute="name")
        level2 = cubes.Level("product", attrs, key="code", label_attribute="name")
        level3 = cubes.Level("product", attrs)
        attrs = cubes.attribute_list(["month", "month_name"])
        level4 = cubes.Level("product", attrs)

        self.assertEqual(level1, level2)
        self.assertNotEqual(level2, level3)
        self.assertNotEqual(level2, level4)

class HierarchyTestCase(unittest.TestCase):
    def setUp(self):
        self.levels = [
            cubes.Level("year", attributes=["year"]),
            cubes.Level("month", attributes=["month", "month_name", "month_sname"]),
            cubes.Level("day", attributes=["day"]),
            cubes.Level("week", attributes=["week"])
        ]
        self.level_names = [level.name for level in self.levels]
        self.dimension = cubes.Dimension("date", levels=self.levels)
        self.hierarchy = cubes.Hierarchy("default", ["year", "month", "day"], self.dimension)

    def test_initialization(self):
        """No dimension on initialization should raise an exception."""
        # self.assertRaises(ModelError, cubes.Hierarchy, "default", [self.levels[0]], None)
        self.assertRaises(ModelError, cubes.Hierarchy, "default", [], self.dimension)
        hier = cubes.Hierarchy("default", [])
        try:
            foo = hier.levels
        except ModelInconsistencyError:
            pass

    def test_operators(self):
        """Hierarchy operators len(), hier[] and level in hier"""
        # __len__
        self.assertEqual(3, len(self.hierarchy))

        # __getitem__ by name
        self.assertEqual(self.levels[1], self.hierarchy[1])

        # __contains__ by name or level
        self.assertTrue(self.levels[1] in self.hierarchy)
        self.assertTrue("year" in self.hierarchy)
        self.assertFalse("flower" in self.hierarchy)

    def test_levels_for(self):
        """Levels for depth"""
        levels = self.hierarchy.levels_for_depth(0)
        self.assertEqual([], levels)

        levels = self.hierarchy.levels_for_depth(1)
        self.assertEqual([self.levels[0]], levels)

        self.assertRaises(ArgumentError, self.hierarchy.levels_for_depth, 4)

    def test_level_ordering(self):
        """Ordering of levels (next, previous)"""
        self.assertEqual(self.levels[0], self.hierarchy.next_level(None))
        self.assertEqual(self.levels[1], self.hierarchy.next_level(self.levels[0]))
        self.assertEqual(self.levels[2], self.hierarchy.next_level(self.levels[1]))
        self.assertEqual(None, self.hierarchy.next_level(self.levels[2]))

        self.assertEqual(None, self.hierarchy.previous_level(None))
        self.assertEqual(None, self.hierarchy.previous_level(self.levels[0]))
        self.assertEqual(self.levels[0], self.hierarchy.previous_level(self.levels[1]))
        self.assertEqual(self.levels[1], self.hierarchy.previous_level(self.levels[2]))

        self.assertEqual(0, self.hierarchy.level_index(self.levels[0]))
        self.assertEqual(1, self.hierarchy.level_index(self.levels[1]))
        self.assertEqual(2, self.hierarchy.level_index(self.levels[2]))

        self.assertRaises(cubes.ArgumentError, self.hierarchy.level_index, self.levels[3])

    def test_rollup(self):
        """Path roll-up for hierarchy"""
        path = [2010,1,5]
        self.assertEqual([2010,1], self.hierarchy.rollup(path))
        self.assertEqual([2010,1], self.hierarchy.rollup(path, "month"))
        self.assertEqual([2010], self.hierarchy.rollup(path, "year"))
        self.assertRaises(ArgumentError, self.hierarchy.rollup, [2010],"month")
        self.assertRaises(ArgumentError, self.hierarchy.rollup, [2010],"unknown")

    def test_base_path(self):
        """Test base paths"""
        self.assertTrue(self.hierarchy.path_is_base([2012,1,5]))
        self.assertFalse(self.hierarchy.path_is_base([2012,1]))
        self.assertFalse(self.hierarchy.path_is_base([2012]))
        self.assertFalse(self.hierarchy.path_is_base([]))

    def test_attributes(self):
        """Collecting attributes and keys"""
        keys = [a.name for a in self.hierarchy.key_attributes()]
        self.assertEqual(["year", "month", "day"], keys)

        attrs = [a.name for a in self.hierarchy.all_attributes()]
        self.assertEqual(["year", "month", "month_name", "month_sname", "day"], attrs)

class DimensionTestCase(unittest.TestCase):
    def setUp(self):
        self.levels = [
            cubes.Level("year", attributes=["year"]),
            cubes.Level("month", attributes=["month", "month_name", "month_sname"]),
            cubes.Level("day", attributes=["day"]),
            cubes.Level("week", attributes=["week"])
        ]
        self.level_names = [level.name for level in self.levels]
        self.dimension = cubes.Dimension("date", levels=self.levels)
        self.hierarchy = cubes.Hierarchy("default", ["year", "month", "day"], self.dimension)

    def test_create(self):
        """Dimension from a dictionary"""
        dim = cubes.create_dimension("year")
        self.assertIsInstance(dim, cubes.Dimension)
        self.assertEqual("year", dim.name)
        self.assertEqual(["year"], [str(a) for a in dim.all_attributes()])

        # Test default: explicit level attributes
        desc = { "name":"date", "levels":["year"] }
        dim = cubes.create_dimension(desc)
        self.assertTrue(dim.is_flat)
        self.assertFalse(dim.has_details)
        self.assertIsInstance(dim, cubes.Dimension)
        self.assertEqual("date", dim.name)
        self.assertEqual(["year"], [str(a) for a in dim.all_attributes()])

        desc = { "name":"date", "levels":["year", "month", "day"] }
        dim = cubes.create_dimension(desc)
        self.assertIsInstance(dim, cubes.Dimension)
        self.assertEqual("date", dim.name)
        names = [str(a) for a in dim.all_attributes()]
        self.assertEqual(["year", "month", "day"], names)
        self.assertFalse(dim.is_flat)
        self.assertFalse(dim.has_details)
        self.assertEqual(3, len(dim.levels))
        for level in dim.levels:
            self.assertIsInstance(level, cubes.Level)
        self.assertEqual(1, len(dim.hierarchies))
        self.assertEqual(3, len(dim.hierarchy()))

        # Test default: implicit single level attributes
        desc = { "name":"product", "attributes":["code", "name"] }
        dim = cubes.create_dimension(desc)
        names = [str(a) for a in dim.all_attributes()]
        self.assertEqual(["code", "name"], names)
        self.assertEqual(1, len(dim.levels))
        self.assertEqual(1, len(dim.hierarchies))

        self.assertRaises(cubes.ModelInconsistencyError,
                     cubes.Dimension, "date", levels=["year", "month"])


    def test_flat_dimension(self):
        """Flat dimension and 'has details' flags"""
        dim = cubes.create_dimension("foo")
        self.assertTrue(dim.is_flat)
        self.assertFalse(dim.has_details)
        self.assertEqual(1, len(dim.levels))

        level=dim.level("foo")
        self.assertIsInstance(level, cubes.Level)
        self.assertEqual("foo", level.name)
        self.assertEqual(1, len(level.attributes))
        self.assertEqual("foo", str(level.key))

        attr=level.attributes[0]
        self.assertIsInstance(attr, cubes.Attribute)
        self.assertEqual("foo", attr.name)

    def test_comparisons(self):
        """Comparison of dimension instances"""

        dim1 = cubes.create_dimension(DIM_DATE_DESC)
        dim2 = cubes.create_dimension(DIM_DATE_DESC)

        self.assertListEqual(dim1.levels, dim2.levels)
        self.assertListEqual(dim1.hierarchies.items(), dim2.hierarchies.items())

        self.assertEqual(dim1, dim2)

    def test_to_dict(self):
        desc = self.dimension.to_dict()
        dim = cubes.create_dimension(desc)

        self.assertEqual(self.dimension.hierarchies, dim.hierarchies)
        self.assertEqual(self.dimension.levels, dim.levels)
        self.assertEqual(self.dimension, dim)

    def test_template(self):
        dims = {"date":self.dimension}
        desc = {"template":"date", "name":"date"}
        dim = cubes.create_dimension(desc, dims)
        self.assertEqual(self.dimension, dim)
        hier = dim.hierarchy()
        self.assertEqual(4, len(hier.levels))

        desc["hierarchy"] = ["year", "month"]
        dim = cubes.create_dimension(desc, dims)
        self.assertEqual(1, len(dim.hierarchies))
        hier = dim.hierarchy()
        self.assertEqual(2, len(hier.levels))

class CubeTestCase(unittest.TestCase):
    def setUp(self):
        a = [DIM_DATE_DESC, DIM_PRODUCT_DESC, DIM_FLAG_DESC]
        self.measures = cubes.attribute_list(["amount", "discount"])
        self.dimensions = [cubes.create_dimension(desc) for desc in a]
        self.cube = cubes.Cube("contracts",
                                dimensions=self.dimensions,
                                measures=self.measures)

    def test_get_dimension(self):
        self.assertListEqual(self.dimensions, self.cube.dimensions)

        self.assertEqual("date", self.cube.dimension("date").name)
        self.assertEqual("product", self.cube.dimension("product").name)
        self.assertEqual("flag", self.cube.dimension("flag").name)
        self.assertRaises(NoSuchDimensionError, self.cube.dimension, "xxx")

    def test_get_measure(self):
        self.assertListEqual(self.measures, self.cube.measures)

        self.assertEqual("amount", self.cube.measure("amount").name)
        self.assertEqual("discount", self.cube.measure("discount").name)
        self.assertRaises(NoSuchAttributeError, self.cube.measure, "xxx")

    def test_to_dict(self):
        desc = self.cube.to_dict()
        dims = dict((dim.name, dim) for dim in self.dimensions)
        cube = cubes.create_cube(desc, dims)
        self.assertEqual(self.cube.dimensions, cube.dimensions)
        self.assertEqual(self.cube.measures, cube.measures)
        self.assertEqual(self.cube, cube)

class ModelTestCase(unittest.TestCase):
    def setUp(self):
        a = [DIM_DATE_DESC, DIM_PRODUCT_DESC, DIM_FLAG_DESC]
        self.measures = cubes.attribute_list(["amount", "discount"])
        self.dimensions = [cubes.create_dimension(desc) for desc in a]
        self.cube = cubes.Cube("contracts",
                                dimensions=self.dimensions,
                                measures=self.measures)
        self.model = cubes.Model(cubes=[self.cube],
                                 dimensions=self.dimensions)
        self.model_path = os.path.join(DATA_PATH, 'model.json')

    def test_creation(self):
        desc = { "dimensions": ["date", "product", "flag"] }
        model = cubes.create_model(desc)
        self.assertEqual(3, len(model.dimensions))
        self.assertEqual(0, len(model.cubes))

        desc = {
                    "dimensions": ["date", "product", "flag"],
                    "cubes": [
                        {
                            "name": "contracts",
                            "dimensions": ["date", "product", "flag"]
                        }
                    ]
                }
        model = cubes.create_model(desc)
        self.assertEqual(3, len(model.dimensions))
        self.assertEqual(1, len(model.cubes))
        self.assertIs(model.dimension("date"), model.cube("contracts").dimension("date"))

        # Test duplicate dimensions
        dup = dict(desc)
        desc["cubes"].append(desc["cubes"][0])
        self.assertRaises(cubes.ModelError, cubes.create_model, dup)

        dup = dict(desc)
        desc["dimensions"].append(desc["dimensions"][0])
        self.assertRaises(cubes.ModelError, cubes.create_model, dup)

    def test_extraction(self):
        self.assertEqual(self.dimensions[0], self.model.dimension("date"))
        self.assertRaises(NoSuchDimensionError, self.model.dimension, "xxx")

        self.assertEqual(self.cube, self.model.cube("contracts"))
        self.assertRaises(ModelError, self.model.cube, "xxx")

    def test_to_dict(self):
        desc = self.model.to_dict()
        model = cubes.create_model(desc)

        self.assertEqual(self.model.dimensions, model.dimensions)
        self.assertEqual(self.model.cubes, model.cubes)
        self.assertEqual(self.model, model)

        desc2 = model.to_dict()
        self.assertEqual(desc, desc2)

    def test_model_from_path(self):
        model = cubes.model_from_path(self.model_path)

        self.assertEqual(model.name, "public_procurements")
        self.assertEqual(len(model.dimensions), 6)
        self.assertEqual('cpv', model.dimension('cpv').name)
        self.assertEqual(len(model.cubes), 1)

        cube = model.cube("contracts")
        self.assertNotEqual(None, cube)
        self.assertEqual(cube.name, "contracts")

class OldModelValidatorTestCase(unittest.TestCase):

    def setUp(self):
        self.model = cubes.Model('test')
        self.date_levels = [ {"name":"year", "key": "year" }, {"name":"month", "key": "month" } ]
        self.date_levels2 = [ { "name":"year", "key": "year" }, {"name":"month", "key": "month" }, {"name":"day", "key":"day"} ]
        self.date_hiers = [ { "name":"ym", "levels": ["year", "month"] } ]
        self.date_hiers2 = [ {"name":"ym", "levels": ["year", "month"] }, 
                             {"name":"ymd", "levels": ["year", "month", "day"] } ]
        self.date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers }

    def test_dimension_validation(self):
        date_desc = { "name": "date", "levels": {"year": {"attributes": ["year"]}}}
        dim = cubes.create_dimension(date_desc)
        self.assertEqual(1, len(dim.levels))
        results = dim.validate()
        self.assertValidation(results, "No levels")
        self.assertValidation(results, "No defaut hierarchy")

        # FIXME: uncomment this after implementing https://github.com/Stiivi/cubes/issues/8
        # self.assertValidationError(results, "No hierarchies in dimension", expected_type = "default")

        date_desc = { "name": "date", "levels": self.date_levels}
        dim = cubes.create_dimension(date_desc)
        results = dim.validate()

        # FIXME: uncomment this after implementing https://github.com/Stiivi/cubes/issues/8
        # self.assertValidationError(results, "No hierarchies in dimension.*more", expected_type = "error")

        date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers }
        dim = cubes.create_dimension(date_desc)
        results = dim.validate()

        self.assertValidation(results, "No levels in dimension", "Dimension is invalid without levels")
        self.assertValidation(results, "No hierarchies in dimension", "Dimension is invalid without hierarchies")
        # self.assertValidationError(results, "No default hierarchy name")

        dim.default_hierarchy_name = 'foo'
        results = dim.validate()
        self.assertValidationError(results, "Default hierarchy .* does not")
        self.assertValidation(results, "No default hierarchy name")

        dim.default_hierarchy_name = 'ym'
        results = dim.validate()
        self.assertValidation(results, "Default hierarchy .* does not")

        # date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers2 }
        # # cubes.Dimension('date', date_desc)
        # self.assertRaisesRegexp(KeyError, 'No level day in dimension', cubes.create_dimension, date_desc)

        date_desc = { "name": "date", "levels": self.date_levels2 , "hierarchies": self.date_hiers2 }
        dim = cubes.create_dimension(date_desc)
        results = dim.validate()
        self.assertValidationError(results, "No defaut hierarchy .* more than one")

    def assertValidation(self, results, expected, message = None):
        if not message:
            message = "Validation pass expected (match: '%s')" % expected

        for result in results:
            if re.match(expected, result[1]):
                self.fail(message)

    def assertValidationError(self, results, expected, message = None, expected_type = None):
        # print "TEST: %s:%s" % (expected_type, expected)
        if not message:
            if expected_type:
                message = "Validation %s expected (match: '%s')" % (expected_type, expected)
            else:
                message = "Validation fail expected (match: '%s')" % expected

        for result in results:
            # print "VALIDATE: %s IN %s:%s" % (expected, result[0], result[1])
            if re.match(expected, result[1]):
                if not expected_type or (expected_type and expected_type == result[0]):
                    return
        self.fail(message)

def test_suite():
    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(AttributeTestCase))
    suite.addTest(unittest.makeSuite(LevelTestCase))
    suite.addTest(unittest.makeSuite(HierarchyTestCase))
    suite.addTest(unittest.makeSuite(DimensionTestCase))
    suite.addTest(unittest.makeSuite(CubeTestCase))
    suite.addTest(unittest.makeSuite(ModelTestCase))

    suite.addTest(unittest.makeSuite(OldModelValidatorTestCase))

    return suite
