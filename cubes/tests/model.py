import unittest
import os
import json
import re
import cubes

from common import DATA_PATH

class ModelTestCase(unittest.TestCase):
	
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        handle = open(self.model_path)
        self.model_dict = json.load(handle)

    def test_dimension_from_file(self):
        info = self.model_dict["dimensions"]["date"]
        dim = cubes.Dimension(**info)

        self.assertEqual(3, len(dim.levels))
        self.assertEqual(2, len(dim.hierarchies))

        self.assertItemsEqual(["year", "month", "day"], dim.level_names,
                                        "invalid levels %s" % dim.level_names)
        self.assertItemsEqual(["default", "ym"], dim.hierarchies.keys(),
                                        "invalid hierarchies %s" % dim.hierarchies.keys())
        self.assertEqual(dim.hierarchies["default"], dim.default_hierarchy, "Default hierarchy does not match")

        hlevels = dim.default_hierarchy.levels
        self.assertEqual(len(hlevels), 3, "Default hierarchy level count is not 3 (%s)" % hlevels)
        

        hlevels = dim.hierarchies["default"].levels
        self.assertTrue(issubclass(hlevels[0].__class__, cubes.Level), "Level should be subclass of Level")
        self.assertEqual(dim.level("year"), hlevels[0], "Level should be equal")

    def test_cube_from_file(self):
        info = self.model_dict["cubes"]["contracts"]
        self.skipTest("Cubes test is not yet implemented")

    def test_model_from_path(self):
        model = cubes.model_from_path(self.model_path)

        self.assertEqual(model.name, "public_procurements", "Model was not properely loaded")
        self.assertEqual(len(model.dimensions), 6)
        self.assertEqual('cpv', model.dimension('cpv').name)
        self.assertEqual(len(model.cubes), 1)
        cube = model.cubes.get("contracts")
        self.assertNotEqual(None, cube, 'No expected "contracts" cube found')
        self.assertEqual(cube.name, "contracts", "Model cube was not properely loaded")

        self.assertModelValid(model)
                
    def model_validation(self):
        self.skipTest("Model validation is not yet implemented")

    def assertModelValid(self, model):
        results = model.validate()
        print "model validation results:"
        for result in results:
            print "  %s: %s" % result

        error_count = 0
        for result in results:
            if result[0] == 'error':
                error_count += 1


        if error_count > 0:
            self.fail("Model validation failed")
            
    def test_flat_dimension(self):
        dim = cubes.Dimension("foo")
        self.assertEqual(True, dim.is_flat)
        self.assertEqual(False, dim.has_details)
        self.assertEqual(1, len(dim.levels))

        level=dim.level("default")
        self.assertEqual(True, isinstance(level, cubes.Level))
        self.assertEqual("default", level.name)
        self.assertEqual(1, len(level.attributes))
        self.assertEqual("foo", str(level.key))

        attr=level.attributes[0]
        self.assertEqual(True, isinstance(attr, cubes.Attribute))
        self.assertEqual("foo", attr.name)

    def test_level_construction(self):
        dim = cubes.Dimension("foo", levels=["category", "subcategory"])
        self.assertEqual(2, len(dim.levels))
        level=dim.level("category")
        self.assertEqual(True, isinstance(level, cubes.Level))
        self.assertEqual("category", level.name)
        self.assertEqual(1, len(level.attributes))
        self.assertEqual("category", str(level.key))

        attr=level.attributes[0]
        self.assertEqual(True, isinstance(attr, cubes.Attribute))
        self.assertEqual("category", attr.name)
        
    def test_dimension_dict_construction(self):
        # Simple dimension: flat, no details
        info = {"name": "city"}
        dim = cubes.Dimension(**info)
        self.assertEqual("city", dim.name)
        self.assertEqual(1, len(dim.levels))

        # Hierarchical dimension, no details
        level_names = ["country", "city"]
        info = {"name": "geography", "levels": level_names}
        dim = cubes.Dimension(**info)
        self.assertEqual("geography", dim.name)
        self.assertEqual(2, len(dim.levels))
        self.assertEqual(level_names, [level.name for level in dim.levels])
        self.assertEqual(level_names, [str(level.key) for level in dim.levels])

        # Hierarchical dimension with details
        levels = [ { "name": "country", "attributes": ["code", "name"]},
                    { "name": "city", "attributes": ["code", "name", "zip"]} ]

        info = {"name": "geography", "levels": levels}

        dim = cubes.Dimension(**info)
        self.assertEqual("geography", dim.name)
        self.assertEqual(2, len(dim.levels))
        self.assertEqual(level_names, [level.name for level in dim.levels])
        self.assertEqual(["code", "code"], [str(level.key) for level in dim.levels])
        

        
class ModelFromDictionaryTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        self.model = cubes.load_model(self.model_path)

    def test_model_from_dictionary(self):
        model_dict = self.model.to_dict()
        new_model = cubes.model.Model(**model_dict)
        new_model_dict = new_model.to_dict()
        
        # Break-down comparison to see where the difference is
        self.assertEqual(model_dict.keys(), new_model_dict.keys(), 'model dictionaries should have same keys')

        for key in model_dict.keys():
            old_value = model_dict[key]
            new_value = new_model_dict[key]

            self.assertEqual(type(old_value), type(new_value), "model part '%s' type should be the same" % key)
            if type(old_value) == dict:
                self.assertDictEqual(old_value, new_value, "model part '%s' should be the same" % key)
                pass
            else:
                self.assertEqual(old_value, new_value, "model part '%s' should be the same" % key)

        self.assertDictEqual(model_dict, new_model_dict, 'model dictionaries should be the same')
    
class ModelValidatorTestCase(unittest.TestCase):

    def setUp(self):
        self.model = cubes.Model('test')
        self.date_levels = { "year": { "key": "year" }, "month": { "key": "month" } }
        self.date_levels2 = { "year": { "key": "year" }, "month": { "key": "month" }, "day": {"key":"day"} }
        self.date_hiers = { "ym": { "levels": ["year", "month"] } }
        self.date_hiers2 = { "ym": { "levels": ["year", "month"] }, 
                             "ymd": { "levels": ["year", "month", "day"] } }
        self.date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers }

    def test_comparisons(self):
        lvl1 = cubes.Level('lvl1', key="year", attributes=["foo", "bar"])
        lvl2 = cubes.Level('lvl1', key="year", attributes=["foo", "bar"])
        lvl3 = cubes.Level('lvl1', key="year", attributes=["bar", "foo"])

        self.assertEqual(lvl1, lvl2)
        self.assertNotEqual(lvl2, lvl3)
        
        dim1 = cubes.Dimension(**self.date_desc)
        dim2 = cubes.Dimension(**self.date_desc)

        self.assertListEqual(dim1.levels, dim2.levels)
        self.assertListEqual(dim1.hierarchies.items(), dim2.hierarchies.items())

        self.assertEqual(dim1, dim2)

    def test_default_dimension(self):
        date_desc = { "name": "date", "levels": {"year": {"key": "year"}}}
        dim = cubes.Dimension(**date_desc)
        h = dim.default_hierarchy
        self.assertEqual("default", h.name)

        date_desc = { "name": "date", "levels": self.date_levels2}
        dim = cubes.Dimension(**date_desc)
        test = lambda: dim.default_hierarchy

        # FIXME: uncomment this after implementing https://github.com/Stiivi/cubes/issues/8
        # self.assertRaises(KeyError, test)

    def test_dimension_types(self):
        date_desc = { "name": "date", "levels": {"year": {"key": "year"}}}
        dim = cubes.Dimension(**date_desc)

        for level in dim.levels:
            self.assertEqual(type(level), cubes.Level)

    def test_dimension_validation(self):
        date_desc = { "name": "date", "levels": {"year": {"key": "year"}}}
        dim = cubes.Dimension(**date_desc)
        self.assertEqual(1, len(dim.levels))
        results = dim.validate()
        self.assertValidation(results, "No levels")
        self.assertValidation(results, "No defaut hierarchy")

        # FIXME: uncomment this after implementing https://github.com/Stiivi/cubes/issues/8
        # self.assertValidationError(results, "No hierarchies in dimension", expected_type = "default")

        date_desc = { "name": "date", "levels": self.date_levels}
        dim = cubes.Dimension(**date_desc)
        results = dim.validate()

        # FIXME: uncomment this after implementing https://github.com/Stiivi/cubes/issues/8
        # self.assertValidationError(results, "No hierarchies in dimension.*more", expected_type = "error")

        date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers }
        dim = cubes.Dimension(**date_desc)
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

        date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers2 }
        # cubes.Dimension('date', date_desc)
        self.assertRaisesRegexp(KeyError, 'No level day in dimension', cubes.Dimension, **date_desc)

        date_desc = { "name": "date", "levels": self.date_levels2 , "hierarchies": self.date_hiers2 }
        dim = cubes.Dimension(**date_desc)
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
        		
def suite():
    suite = unittest.TestSuite()

    suite.addTest(unittest.makeSuite(ModelValidatorTestCase))
    suite.addTest(unittest.makeSuite(ModelFromDictionaryTestCase))
    suite.addTest(unittest.makeSuite(ModelTestCase))

    return suite
