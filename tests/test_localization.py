import unittest
from cubes import Namespace
from cubes import StaticModelProvider
from cubes import read_json_file
from cubes.metadata.localization import LocalizationContext, ModelObjectLocalizationContext
from .common import CubesTestCaseBase

class LocalizationTestCase(CubesTestCaseBase):
    def setUp(self):
        super(LocalizationTestCase, self).setUp()
        self.translation = read_json_file(self.model_path("translation.json"))
        self.model = read_json_file(self.model_path("localizable.json"))
        self.provider = StaticModelProvider(self.model)
        self.context = LocalizationContext(self.translation)
    def test_basic(self):
        trans = self.context.object_localization("cubes", "inner")
        self.assertEqual(trans.get("label"), "inner_LAB")
        self.assertEqual(trans.get("description"), "inner_DESC")

        trans = self.context.object_localization("dimensions", "date")
        self.assertEqual(trans.get("label"), "date_LAB")

    def test_child(self):
        trans = self.context.object_localization("cubes", "inner")
        trans = trans.object_localization("measures", "deeper")

        self.assertEqual(trans.get("label"), "deeper_LAB")

    def test_global(self):
        trans = self.context.object_localization("cubes", "useglobal")
        trans = trans.object_localization("measures", "amount")

        self.assertIsInstance(trans, ModelObjectLocalizationContext)

        self.assertEqual(trans.get("label"), "amount_OUT_LAB")

    def test_missing(self):
        trans = self.context.object_localization("cubes", "MISSING")
        self.assertIsInstance(trans, ModelObjectLocalizationContext)

        trans = self.context.object_localization("cubes", "useglobal")
        trans = trans.object_localization("measures", "UNKNOWN")
        self.assertIsInstance(trans, ModelObjectLocalizationContext)

        self.assertIs(trans.get("label"), None)
        self.assertIs(trans.get("label", "DEFAULT"), "DEFAULT")

    def test_translate_cube(self):
        cube = self.provider.cube("inner")
        self.assertEqual(cube.label, "inner_ORIGINAL")

        trans = self.context.object_localization("cubes", "inner")
        cube = cube.localized(trans)
        self.assertEqual(cube.label, "inner_LAB")

    # TODO: test non existent top object
    # TODO: test non existend child object
    # TODO: test plain label

