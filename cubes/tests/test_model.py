import unittest
import os
import cubes
from cubes.tests import DATA_PATH
import json
import re

class ModelTestCase(unittest.TestCase):
	
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        handle = open(self.model_path)
        self.model_dict = json.load(handle)

    def test_dimension_from_file(self):
        info = self.model_dict["dimensions"]["date"]
        dim = cubes.Dimension("date", info)
        self.assertEqual(len(dim.levels), 3, "invalid number of levels for date dimension")
        self.assertEqual(len(dim.hierarchies), 2, "invalid number of hierarchies for date dimension")
        self.assertItemsEqual(dim.level_names, ["year", "month", "day"],
                                        "invalid levels %s" % dim.level_names)
        self.assertItemsEqual(dim.hierarchies.keys(), ["default", "ym"],
                                        "invalid hierarchies %s" % dim.hierarchies.keys())
        self.assertEqual(dim.hierarchies["default"], dim.default_hierarchy, "Default hierarchy does not match")

        hlevels = dim.default_hierarchy.levels
        self.assertEqual(len(hlevels), 3, "Default hierarchy level count is not 3 (%s)" % hlevels)
        

        hlevels = dim.hierarchies["default"].levels
        self.assertTrue(issubclass(hlevels[0].__class__, cubes.Level), "Level should be subclass of Level")
        self.assertEqual(dim.level("year"), hlevels[0], "Level should be equal")

    def test_cube_from_file(self):
        info = self.model_dict["cubes"]["contracts"]
        self.skipTest("Cubes are not yet implemented")

    def test_model_from_path(self):
        model = cubes.model_from_path(self.model_path)
        self.assertEqual(model.name, "public_procurements", "Model was not properely loaded")
        self.assertEqual(len(model.dimensions), 6, "Model dimensions were not properely loaded")
        self.assertEqual(len(model.cubes), 1, "Model cubes were not loaded")
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
        
class ModelFromDictionaryTestCase(unittest.TestCase):
    def setUp(self):
        self.model_path = os.path.join(DATA_PATH, 'model.json')
        self.model = cubes.model_from_path(self.model_path)

    def test_model_from_dictionary(self):
        model_dict = self.model.to_dict()
        new_model = cubes.model_from_dict(model_dict)
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
        lvl1 = cubes.Level('lvl1', {"key": "year", "attributes": ["foo", "bar"]})
        lvl2 = cubes.Level('lvl1', {"key": "year", "attributes": ["foo", "bar"]})
        lvl3 = cubes.Level('lvl1', {"key": "year", "attributes": ["bar", "foo"]})

        self.assertEqual(lvl1, lvl2)
        self.assertNotEqual(lvl2, lvl3)
        
        dim1 = cubes.Dimension('date', self.date_desc)
        dim2 = cubes.Dimension('date', self.date_desc)

        self.assertListEqual(dim1.levels, dim2.levels)
        self.assertListEqual(dim1.hierarchies.items(), dim2.hierarchies.items())

        self.assertEqual(dim1, dim2)

    def test_default_dimension(self):
        date_desc = { "name": "date", "levels": {"year": {"key": "year"}}}
        dim = cubes.Dimension('date', date_desc)
        h = dim.default_hierarchy
        self.assertEqual("year", h.name)

        date_desc = { "name": "date", "levels": self.date_levels2}
        dim = cubes.Dimension('date', date_desc)
        test = lambda: dim.default_hierarchy
        self.assertRaises(KeyError, test)
        
        date_desc = { "name": "date", "levels": {}}
        dim = cubes.Dimension('date', date_desc)
        test = lambda: dim.default_hierarchy
        self.assertRaises(KeyError, test)

    def test_dimension_types(self):
        date_desc = { "name": "date", "levels": {"year": {"key": "year"}}}
        dim = cubes.Dimension('date', date_desc)

        for level in dim.levels:
            self.assertEqual(type(level), cubes.Level)

    def test_dimension_validation(self):
        date_desc = { "name": "date"}
        dim = cubes.Dimension('date', date_desc)
        results = dim.validate()
        self.assertValidationError(results, "No levels in dimension")

        date_desc = { "name": "date", "levels": {"year": {"key": "year"}}}
        dim = cubes.Dimension('date', date_desc)
        self.assertEqual(1, len(dim.levels))
        results = dim.validate()
        self.assertValidation(results, "No levels")
        self.assertValidation(results, "No defaut hierarchy")

        self.assertValidationError(results, "No hierarchies in dimension", expected_type = "default")

        date_desc = { "name": "date", "levels": self.date_levels}
        dim = cubes.Dimension('date', date_desc)
        results = dim.validate()

        self.assertValidationError(results, "No hierarchies in dimension.*more", expected_type = "error")

        date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers }
        dim = cubes.Dimension('date', date_desc)
        results = dim.validate()

        self.assertValidation(results, "No levels in dimension", "Dimension is invalid without levels")
        self.assertValidation(results, "No hierarchies in dimension", "Dimension is invalid without hierarchies")
        self.assertValidationError(results, "No default hierarchy name")
        
        dim.default_hierarchy_name = 'foo'
        results = dim.validate()
        self.assertValidationError(results, "Default hierarchy .* does not")
        self.assertValidation(results, "No default hierarchy name")

        dim.default_hierarchy_name = 'ym'
        results = dim.validate()
        self.assertValidation(results, "Default hierarchy .* does not")

        date_desc = { "name": "date", "levels": self.date_levels , "hierarchies": self.date_hiers2 }
        # cubes.Dimension('date', date_desc)
        self.assertRaisesRegexp(KeyError, 'No level day in dimension', cubes.Dimension, 'date', date_desc)

        date_desc = { "name": "date", "levels": self.date_levels2 , "hierarchies": self.date_hiers2 }
        dim = cubes.Dimension('date', date_desc)
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
        		
if __name__ == '__main__':
    unittest.main()

