import unittest
import os
import re

from cubes import read_model_metadata, read_model_metadata_bundle
from cubes.errors import ArgumentError, ModelError, HierarchyError
from cubes.errors import ModelInconsistencyError, NoSuchAttributeError
from cubes.errors import NoSuchDimensionError
from cubes.metadata import Level, Attribute, Measure, MeasureAggregate
from cubes.metadata import create_list_of
from cubes.metadata import Dimension, Hierarchy, Cube

import copy
from .common import TESTS_PATH, CubesTestCaseBase

DIM_DATE_DESC = {
    "name": "date",
    "levels": [
        {"name": "year"},
        {"name": "month", "attributes": ["month", "month_name"]},
        {"name": "day"}
    ],
    "hierarchies": [
        {"name": "ymd", "levels": ["year", "month", "day"]},
        {"name": "ym", "levels": ["year", "month"]},
    ]
}

DIM_FLAG_DESC = {"name": "flag"}

DIM_PRODUCT_DESC = {
    "name": "product",
    "levels": [
        {"name": "category", "attributes": ["key", "name"]},
        {"name": "subcategory", "attributes": ["key", "name"]},
        {"name": "product", "attributes": ["key", "name", "description"]}
    ]
}


class ModelTestCaseBase(unittest.TestCase):
    def setUp(self):
        self.models_path = os.path.join(TESTS_PATH, 'models')

    def model_path(self, model):
        return os.path.join(self.models_path, model)


class AttributeTestCase(unittest.TestCase):
    """docstring for AttributeTestCase"""
    def test_basics(self):
        """Attribute creation and attribute references"""
        attr = Attribute("foo")
        self.assertEqual("foo", attr.name)
        self.assertEqual("foo", str(attr))
        self.assertEqual("foo", attr.ref)

    def test_locale(self):
        """References to localizable attributes"""

        attr = Attribute("foo")
        self.assertRaises(ArgumentError, attr.localized_ref, locale="xx")

        attr = Attribute("foo", locales=["en", "sk"])
        self.assertEqual("foo", attr.name)
        self.assertEqual("foo", str(attr))
        self.assertEqual("foo.en", attr.localized_ref("en"))
        self.assertEqual("foo.sk", attr.localized_ref("sk"))
        self.assertRaises(ArgumentError, attr.localized_ref, locale="xx")

    def test_simplify(self):
        """Simplification of attribute reference (with and without details)"""

        level = Level("name", attributes=[Attribute("name")])
        dim = Dimension("group", levels=[level])
        attr = dim.attribute("name")
        self.assertEqual("name", attr.name)

        # Simplified -> dimension name
        self.assertEqual("group.name", str(attr))
        self.assertEqual("group.name", attr.ref)

        level = Level("name", attributes=[Attribute("key"), Attribute("name")])
        dim = Dimension("group", levels=[level])
        attr = dim.attribute("name")
        self.assertEqual("name", attr.name)
        self.assertEqual("group.name", str(attr))
        self.assertEqual("group.name", attr.ref)

    def test_create_attribute(self):
        """Coalesce attribute object (string or Attribute instance)"""

        level = Level("name", attributes=[Attribute("key"), Attribute("name")])
        dim = Dimension("group", levels=[level])

        obj = Attribute.from_metadata("name")
        self.assertIsInstance(obj, Attribute)
        self.assertEqual("name", obj.name)

        obj = Attribute.from_metadata({"name": "key"})
        obj.dimension = dim
        self.assertIsInstance(obj, Attribute)
        self.assertEqual("key", obj.name)
        self.assertEqual(dim, obj.dimension)

        attr = dim.attribute("key")
        obj = Attribute.from_metadata(attr)
        obj.dimension = dim
        self.assertIsInstance(obj, Attribute)
        self.assertEqual("key", obj.name)
        self.assertEqual(obj, attr)


class MeasuresTestsCase(CubesTestCaseBase):
    def setUp(self):
        super(MeasuresTestsCase, self).setUp()
        self.metadata = self.model_metadata("measures.json")

        self.cubes_md = {}

        for cube in self.metadata["cubes"]:
            self.cubes_md[cube["name"]] = cube

    def cube(self, name):
        """Create a cube object `name` from measures test model."""
        return Cube.from_metadata(self.cubes_md[name])

    def test_basic(self):
        md = {}
        with self.assertRaises(ModelError):
            measure = Measure.from_metadata(md)

        measure = Measure.from_metadata("amount")
        self.assertIsInstance(measure, Measure)
        self.assertEqual("amount", measure.name)

        md = {"name": "amount"}
        measure = Measure.from_metadata(md)
        self.assertEqual("amount", measure.name)

    def test_copy(self):
        md = {"name": "amount"}
        measure = Measure.from_metadata(md)
        measure2 = copy.deepcopy(measure)
        self.assertEqual(measure, measure2)

    def test_aggregate(self):
        md = {}
        with self.assertRaises(ModelError):
            measure = MeasureAggregate.from_metadata(md)

        measure = MeasureAggregate.from_metadata("amount_sum")
        self.assertIsInstance(measure, MeasureAggregate)
        self.assertEqual("amount_sum", measure.name)

    def test_create_default_aggregates(self):
        measure = Measure.from_metadata("amount")
        aggs = measure.default_aggregates()
        self.assertEqual(1, len(aggs))
        agg = aggs[0]
        self.assertEqual("amount_sum", agg.name)
        self.assertEqual("amount", agg.measure)
        self.assertEqual("sum", agg.function)
        self.assertIsNone(agg.formula)

        md = {"name": "amount", "aggregates": ["sum", "min"]}
        measure = Measure.from_metadata(md)
        aggs = measure.default_aggregates()
        self.assertEqual(2, len(aggs))
        self.assertEqual("amount_sum", aggs[0].name)
        self.assertEqual("amount", aggs[0].measure)
        self.assertEqual("sum", aggs[0].function)
        self.assertIsNone(aggs[0].formula)

        self.assertEqual("amount_min", aggs[1].name)
        self.assertEqual("amount", aggs[1].measure)
        self.assertEqual("min", aggs[1].function)
        self.assertIsNone(aggs[1].formula)

    def test_fact_count(self):
        md = {"name": "count", "function": "count"}
        agg = MeasureAggregate.from_metadata(md)

        self.assertEqual("count", agg.name)
        self.assertIsNone(agg.measure)
        self.assertEqual("count", agg.function)
        self.assertIsNone(agg.formula)

    def test_empty2(self):
        """No measures in metadata should yield count measure with record
        count"""
        cube = self.cube("empty")
        self.assertIsInstance(cube, Cube)
        self.assertEqual(0, len(cube.measures))
        self.assertEqual(1, len(cube.aggregates))

        aggregate = cube.aggregates[0]
        self.assertEqual("fact_count", aggregate.name)
        self.assertEqual("count", aggregate.function)
        self.assertIsNone(aggregate.measure)

    def test_amount_default(self):
        """Plain measure definition should yield measure_sum aggregate"""
        cube = self.cube("amount_default")
        measures = cube.measures
        self.assertEqual(1, len(measures))
        self.assertEqual("amount", measures[0].name)
        self.assertIsNone(measures[0].expression)

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual("amount_sum", aggregates[0].name)
        self.assertEqual("amount", aggregates[0].measure)
        self.assertIsNone(aggregates[0].expression)

    def test_fact_count2(self):
        cube = self.cube("fact_count")
        measures = cube.measures
        self.assertEqual(0, len(measures))

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual("total_events", aggregates[0].name)
        self.assertIsNone(aggregates[0].measure)
        self.assertIsNone(aggregates[0].expression)

    def test_amount_sum(self):
        cube = self.cube("amount_sum")
        measures = cube.measures
        self.assertEqual(1, len(measures))
        self.assertEqual("amount", measures[0].name)
        self.assertIsNone(measures[0].expression)

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual("amount_sum", aggregates[0].name)
        self.assertEqual("sum", aggregates[0].function)
        self.assertEqual("amount", aggregates[0].measure)
        self.assertIsNone(aggregates[0].expression)

    def test_explicit_implicit_combined(self):
        # Test explicit aggregates
        #
        cube = self.cube("amount_sum_explicit")
        measures = cube.measures
        self.assertEqual(1, len(measures))
        self.assertEqual("amount", measures[0].name)
        self.assertIsNone(measures[0].expression)

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual("total", aggregates[0].name)
        self.assertEqual("amount", aggregates[0].measure)
        self.assertIsNone(aggregates[0].expression)

        cube = self.cube("amount_sum_combined")
        measures = cube.measures
        self.assertEqual(1, len(measures))
        self.assertEqual("amount", measures[0].name)
        self.assertIsNone(measures[0].expression)

        aggregates = cube.aggregates
        self.assertEqual(3, len(aggregates))
        names = [a.name for a in aggregates]
        self.assertSequenceEqual(["total",
                                  "amount_min",
                                  "amount_max"], names)

    def test_backend_provided(self):
        cube = self.cube("backend_provided_aggregate")
        measures = cube.measures
        self.assertEqual(0, len(measures))

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual("total", aggregates[0].name)
        self.assertIsNone(aggregates[0].measure)
        self.assertIsNone(aggregates[0].expression)

    def measure_expression(self):
        cube = self.cube("measure_expression")
        measures = cube.measures
        self.assertEqual(3, len(measures))

        self.assertEqual("price", measures[0].name)
        self.assertIsNone(measures[0].expression)
        self.assertEqual("costs", measures[1].name)
        self.assertIsNone(measures[2].expression)

        self.assertEqual("revenue", measures[2].name)
        self.assertEqual("price - costs", measures[2].expression)

        aggregates = cube.aggregates
        self.assertEqual(3, len(aggregates))
        self.assertEqual("price_sum", aggregates[0].name)
        self.assertEqual("price", aggregates[0].measure)
        self.assertEqual("costs_sum", aggregates[0].name)
        self.assertEqual("costs", aggregates[0].measure)
        self.assertEqual("revenue_sum", aggregates[0].name)
        self.assertEqual("revenue", aggregates[0].measure)

    # TODO: aggregate_expression, aggregate_expression_error
    # TODO: measure_expression, invalid_expression

    def test_implicit(self):
        # TODO: this should be in model.py tests
        cube = self.cube("default_aggregates")
        aggregates = [a.name for a in cube.aggregates]
        self.assertSequenceEqual(["amount_sum",
                                  "amount_min",
                                  "amount_max"
                                  ],
                                  aggregates)

    def test_explicit(self):
        cube = self.cube("explicit_aggregates")
        aggregates = [a.name for a in cube.aggregates]
        self.assertSequenceEqual(["amount_sum",
                                  "amount_wma",
                                  "count",
                                  ],
                                  aggregates)

    def test_explicit_conflict(self):
        with self.assertRaisesRegex(ModelError, "function mismatch"):
            cube = self.cube("explicit_aggregates_conflict")


class LevelTestCase(unittest.TestCase):
    """docstring for LevelTestCase"""
    def test_initialization(self):
        """Empty attribute list for new level should raise an exception """
        self.assertRaises(ModelError, Level, "month", [])

    def test_has_details(self):
        """Level "has_details" flag"""
        attrs = [Attribute("year")]
        level = Level("year", attrs)
        self.assertFalse(level.has_details)

        attrs = [Attribute("month"), Attribute("month_name")]
        level = Level("month", attrs)
        self.assertTrue(level.has_details)

    def test_operators(self):
        """Level to string conversion"""
        attrs = [Attribute("foo")]
        self.assertEqual("date", str(Level("date", attrs)))

    def test_create(self):
        """Create level from a dictionary"""
        desc = "year"
        level = Level.from_metadata(desc)
        self.assertIsInstance(level, Level)
        self.assertEqual("year", level.name)
        self.assertEqual(["year"], [str(a) for a in level.attributes])

        # Test default: Attributes
        desc = {"name": "year"}
        level = Level.from_metadata(desc)
        self.assertIsInstance(level, Level)
        self.assertEqual("year", level.name)
        self.assertEqual(["year"], [str(a) for a in level.attributes])

        # Test default: Attributes
        desc = {"name": "year", "attributes": ["key"]}
        level = Level.from_metadata(desc)
        self.assertIsInstance(level, Level)
        self.assertEqual("year", level.name)
        self.assertEqual(["key"], [str(a) for a in level.attributes])
        self.assertFalse(level.has_details)

        desc = {"name": "year", "attributes": ["key", "label"]}
        level = Level.from_metadata(desc)
        self.assertTrue(level.has_details)
        self.assertEqual(["key", "label"], [str(a) for a in level.attributes])

        # Level from description with full details
        desc = {
            "name": "month",
            "attributes": [
                {"name": "month"},
                {"name": "month_name", "locales": ["en", "sk"]},
                {"name": "month_sname", "locales": ["en", "sk"]}
            ]
        }

        level = Level.from_metadata(desc)
        self.assertTrue(level.has_details)
        self.assertEqual(3, len(level.attributes))
        names = [str(a) for a in level.attributes]
        self.assertEqual(["month", "month_name", "month_sname"], names)

    def test_key_label_attributes(self):
        """Test key and label attributes - explicit and implicit"""

        attrs = [Attribute("code")]
        level = Level("product", attrs)
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, Attribute)
        self.assertEqual("code", str(level.label_attribute))

        attrs = [Attribute("code"), Attribute("name")]
        level = Level("product", attrs)
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, Attribute)
        self.assertEqual("name", str(level.label_attribute))

        attrs = [Attribute("info"), Attribute("code"), Attribute("name")]
        level = Level("product", attrs, key="code",
                            label_attribute="name")
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, Attribute)
        self.assertEqual("name", str(level.label_attribute))

        # Test key/label in full desc
        desc = {
            "name": "product",
            "attributes": ["info", "code", "name"],
            "label_attribute": "name",
            "key": "code"
        }

        level = Level.from_metadata(desc)
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual("code", str(level.key))
        self.assertIsInstance(level.label_attribute, Attribute)
        self.assertEqual("name", str(level.label_attribute))

    def test_level_inherit(self):
        desc = {
            "name": "product_type",
            "label": "Product Type"
        }

        level = Level.from_metadata(desc)
        self.assertEqual(1, len(level.attributes))

        attr = level.attributes[0]
        self.assertEqual("product_type", attr.name)
        self.assertEqual("Product Type", attr.label)


    def test_comparison(self):
        """Comparison of level instances"""

        attrs = [Attribute("info"), Attribute("code"), Attribute("name")]
        level1 = Level("product", attrs, key="code",
                             label_attribute="name")
        level2 = Level("product", attrs, key="code",
                             label_attribute="name")
        level3 = Level("product", attrs)
        attrs = [Attribute("month"), Attribute("month_name")]
        level4 = Level("product", attrs)

        self.assertEqual(level1, level2)
        self.assertNotEqual(level2, level3)
        self.assertNotEqual(level2, level4)


class HierarchyTestCase(unittest.TestCase):
    def setUp(self):
        self.levels = [
            Level("year", attributes=[Attribute("year")]),
            Level("month",
                  attributes=[
                    Attribute("month"),
                    Attribute("month_name"),
                    Attribute("month_sname")
                ]),
            Level("day", attributes=[Attribute("day")]),
            Level("week", attributes=[Attribute("week")])
        ]
        self.level_names = [level.name for level in self.levels]
        self.dimension = Dimension("date", levels=self.levels)
        levels = [self.levels[0], self.levels[1], self.levels[2]]
        self.hierarchy = Hierarchy("default",
                                         levels)

    def test_initialization(self):
        """No dimension on initialization should raise an exception."""
        with self.assertRaisesRegex(ModelInconsistencyError, "not be empty"):
            Hierarchy("default", [])

        with self.assertRaisesRegex(ModelInconsistencyError, "as strings"):
            Hierarchy("default", ["iamastring"])

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

        self.assertRaises(HierarchyError, self.hierarchy.levels_for_depth, 4)

    def test_level_ordering(self):
        """Ordering of levels (next, previous)"""
        self.assertEqual(self.levels[0], self.hierarchy.next_level(None))
        self.assertEqual(self.levels[1],
                         self.hierarchy.next_level(self.levels[0]))
        self.assertEqual(self.levels[2],
                         self.hierarchy.next_level(self.levels[1]))
        self.assertEqual(None, self.hierarchy.next_level(self.levels[2]))

        self.assertEqual(None, self.hierarchy.previous_level(None))
        self.assertEqual(None, self.hierarchy.previous_level(self.levels[0]))
        self.assertEqual(self.levels[0],
                         self.hierarchy.previous_level(self.levels[1]))
        self.assertEqual(self.levels[1],
                         self.hierarchy.previous_level(self.levels[2]))

        self.assertEqual(0, self.hierarchy.level_index(self.levels[0]))
        self.assertEqual(1, self.hierarchy.level_index(self.levels[1]))
        self.assertEqual(2, self.hierarchy.level_index(self.levels[2]))

        self.assertRaises(HierarchyError, self.hierarchy.level_index,
                          self.levels[3])

    def test_rollup(self):
        """Path roll-up for hierarchy"""
        path = [2010, 1, 5]

        self.assertEqual([2010, 1], self.hierarchy.rollup(path))
        self.assertEqual([2010, 1], self.hierarchy.rollup(path, "month"))
        self.assertEqual([2010], self.hierarchy.rollup(path, "year"))
        self.assertRaises(HierarchyError, self.hierarchy.rollup,
                          [2010], "month")
        self.assertRaises(HierarchyError, self.hierarchy.rollup,
                          [2010], "unknown")

    def test_base_path(self):
        """Test base paths"""
        self.assertTrue(self.hierarchy.path_is_base([2012, 1, 5]))
        self.assertFalse(self.hierarchy.path_is_base([2012, 1]))
        self.assertFalse(self.hierarchy.path_is_base([2012]))
        self.assertFalse(self.hierarchy.path_is_base([]))

    def test_attributes(self):
        """Collecting attributes and keys"""
        keys = [a.name for a in self.hierarchy.key_attributes()]
        self.assertEqual(["year", "month", "day"], keys)

        attrs = [a.name for a in self.hierarchy.all_attributes]
        self.assertEqual(["year", "month", "month_name", "month_sname", "day"],
                         attrs)

    def test_copy(self):
        class DummyDimension(object):
            def __init__(self):
                self.name = "dummy"
                self.is_flat = False

        left = self.hierarchy.levels[0].attributes[0]
        left.dimension = DummyDimension()

        clone = copy.deepcopy(self.hierarchy)

        left = self.hierarchy.levels[0].attributes[0]
        right = clone.levels[0].attributes[0]
        # Make sure that the dimension is not copied
        self.assertIsNone(right.dimension)

        self.assertEqual(self.hierarchy.levels, clone.levels)
        self.assertEqual(self.hierarchy, clone)


class DimensionTestCase(unittest.TestCase):
    def setUp(self):
        self.levels = [
            Level("year", attributes=create_list_of(Attribute, ["year"])),
            Level("month", attributes=create_list_of(Attribute, ["month", "month_name",
                                             "month_sname"])),
            Level("day", attributes=create_list_of(Attribute, ["day"])),
            Level("week", attributes=create_list_of(Attribute, ["week"]))
        ]
        self.level_names = [level.name for level in self.levels]
        self.dimension = Dimension("date", levels=self.levels)

        levels = [self.levels[0], self.levels[1], self.levels[2]]
        self.hierarchy = Hierarchy("default", levels)

    def test_create(self):
        """Dimension from a dictionary"""
        dim = Dimension.from_metadata("year")
        self.assertIsInstance(dim, Dimension)
        self.assertEqual("year", dim.name)
        self.assertEqual(["year.year"], [str(a) for a in dim.attributes])

        # Test default: explicit level attributes
        desc = {"name": "date", "levels": ["year"]}
        dim = Dimension.from_metadata(desc)
        self.assertTrue(dim.is_flat)
        self.assertFalse(dim.has_details)
        self.assertIsInstance(dim, Dimension)
        self.assertEqual("date", dim.name)

        # Dimension string is a reference and is equal to dimension name if
        # dimension is flat
        self.assertEqual(["date.year"], [str(a) for a in dim.attributes])

        desc = {"name": "date", "levels": ["year", "month", "day"]}
        dim = Dimension.from_metadata(desc)
        self.assertIsInstance(dim, Dimension)
        self.assertEqual("date", dim.name)
        refs = [str(a) for a in dim.attributes]
        self.assertEqual(["date.year", "date.month", "date.day"], refs)
        self.assertFalse(dim.is_flat)
        self.assertFalse(dim.has_details)
        self.assertEqual(3, len(dim.levels))
        for level in dim.levels:
            self.assertIsInstance(level, Level)
        self.assertEqual(1, len(dim.hierarchies))
        self.assertEqual(3, len(dim.hierarchy()))

        # Test default: implicit single level attributes
        desc = {"name": "product", "attributes": ["code", "name"]}
        dim = Dimension.from_metadata(desc)
        refs = [str(a) for a in dim.attributes]
        self.assertEqual(["product.code", "product.name"], refs)
        self.assertEqual(1, len(dim.levels))
        self.assertEqual(1, len(dim.hierarchies))

    def test_flat_dimension(self):
        """Flat dimension and 'has details' flags"""
        dim = Dimension.from_metadata("foo")
        self.assertTrue(dim.is_flat)
        self.assertFalse(dim.has_details)
        self.assertEqual(1, len(dim.levels))

        level = dim.level("foo")
        self.assertIsInstance(level, Level)
        self.assertEqual("foo", level.name)
        self.assertEqual(1, len(level.attributes))
        self.assertEqual("foo.foo", str(level.key))

        attr = level.attributes[0]
        self.assertIsInstance(attr, Attribute)
        self.assertEqual("foo", attr.name)

    def test_comparisons(self):
        """Comparison of dimension instances"""

        dim1 = Dimension.from_metadata(DIM_DATE_DESC)
        dim2 = Dimension.from_metadata(DIM_DATE_DESC)

        self.assertListEqual(dim1.levels, dim2.levels)
        self.assertListEqual(dim1.hierarchies, dim2.hierarchies)

        self.assertEqual(dim1, dim2)

    def test_to_dict(self):
        desc = self.dimension.to_dict()
        dim = Dimension.from_metadata(desc)

        self.assertEqual(self.dimension.hierarchies, dim.hierarchies)
        self.assertEqual(self.dimension.levels, dim.levels)
        self.assertEqual(self.dimension, dim)

    def test_template(self):
        dims = {"date": self.dimension}
        desc = {"template": "date", "name": "date"}

        dim = Dimension.from_metadata(desc, dims)
        self.assertEqual(self.dimension, dim)
        hier = dim.hierarchy()
        self.assertEqual(4, len(hier.levels))

        desc["hierarchy"] = ["year", "month"]
        dim = Dimension.from_metadata(desc, dims)
        self.assertEqual(1, len(dim.hierarchies))
        hier = dim.hierarchy()
        self.assertEqual(2, len(hier.levels))

        template = self.dimension.to_dict()
        template["hierarchies"] = [
            {"name": "ym", "levels": ["year", "month"]},
            {"name": "ymd", "levels": ["year", "month", "day"]}
        ]

        template["default_hierarchy_name"] = "ym"
        template = Dimension.from_metadata(template)
        dims = {"date": template}
        desc = {"template": "date", "name":"another_date"}
        dim = Dimension.from_metadata(desc, dims)
        self.assertEqual(2, len(dim.hierarchies))
        self.assertEqual(["ym", "ymd"],
                         [hier.name for hier in dim.hierarchies])

    def test_template_hierarchies(self):
        md = {
            "name": "time",
            "levels": ["year", "month", "day", "hour"],
            "hierarchies": [
                {"name": "full", "levels": ["year", "month", "day", "hour"]},
                {"name": "ymd", "levels": ["year", "month", "day"]},
                {"name": "ym", "levels": ["year", "month"]},
                {"name": "y", "levels": ["year"]},
            ]
        }
        dim_time = Dimension.from_metadata(md)
        templates = {"time": dim_time}
        md = {
            "name": "date",
            "template": "time",
            "hierarchies": [
                "ymd", "ym", "y"
            ]
        }

        dim_date = Dimension.from_metadata(md, templates)

        self.assertEqual(dim_date.name, "date")
        self.assertEqual(len(dim_date.hierarchies), 3)
        names = [h.name for h in dim_date.hierarchies]
        self.assertEqual(["ymd", "ym", "y"], names)

    def test_template_info(self):
        md = {
            "name": "template",
            "levels": [
                { "name": "one", "info": {"units":"$", "format": "foo"}}
            ]
        }
        tempdim = Dimension.from_metadata(md)

        md = {
            "name": "dim",
            "levels": [
                { "name": "one", "info": {"units":"USD"}}
            ],
            "template": "template"
        }

        templates = {"template": tempdim}
        dim = Dimension.from_metadata(md, templates)

        level = dim.level("one")
        self.assertIn("units", level.info)
        self.assertIn("format", level.info)
        self.assertEqual(level.info["units"], "USD")
        self.assertEqual(level.info["format"], "foo")

class CubeTestCase(unittest.TestCase):
    def setUp(self):
        a = [DIM_DATE_DESC, DIM_PRODUCT_DESC, DIM_FLAG_DESC]
        self.measures = create_list_of(Measure, ["amount", "discount"])
        self.details = create_list_of(Attribute, ["detail"])
        self.dimensions = [Dimension.from_metadata(desc) for desc in a]
        self.cube = Cube("contracts",
                                dimensions=self.dimensions,
                                measures=self.measures,
                                details=self.details)

    def test_create_cube(self):
        cube = {
                "name": "cube",
                "dimensions": ["date"],
                "aggregates": ["record_count"],
                "details": ["some_detail", "another_detail"]
        }
        cube = Cube.from_metadata(cube)

        self.assertEqual(cube.name, "cube")
        self.assertEqual(len(cube.aggregates), 1)
        self.assertEqual(len(cube.details), 2)

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

    def test_attributes(self):
        all_attributes = self.cube.all_attributes

        refs = [a.ref for a in all_attributes]
        expected = [
            'date.year',
            'date.month',
            'date.month_name',
            'date.day',
            'product.key',
            'product.name',
            'product.description',
            'flag.flag',
            'detail',
            'amount',
            'discount']
        self.assertSequenceEqual(expected, refs)

        attributes = self.cube.get_attributes(["date.year", "product.name"])
        refs = [a.ref for a in attributes]
        expected = ['date.year', 'product.name']
        self.assertSequenceEqual(expected, refs)

        attributes = self.cube.get_attributes(["amount"])
        refs = [a.ref for a in attributes]
        self.assertSequenceEqual(["amount"], refs)

        with self.assertRaises(NoSuchAttributeError):
            self.cube.get_attributes(["UNKNOWN"])

    @unittest.skip("deferred (needs workspace)")
    def test_to_dict(self):
        desc = self.cube.to_dict()
        dims = dict((dim.name, dim) for dim in self.dimensions)
        cube = Cube.from_metadata(desc, dims)
        self.assertEqual(self.cube.dimensions, cube.dimensions)
        self.assertEqual(self.cube.measures, cube.measures)
        self.assertEqual(self.cube, cube)

    @unittest.skip("requires revision")
    def test_links(self):
        # TODO: test link alias!
        dims = dict((d.name, d) for d in self.dimensions)

        links = [{"name": "date"}]
        cube = Cube("contracts",
                          dimension_links=links,
                          measures=self.measures)
        cube.link_dimensions(dims)
        self.assertEqual(len(cube.dimensions), 1)
        dim = cube.dimension("date")
        self.assertEqual(len(dim.hierarchies), 2)

        links = [{"name": "date"}, "product", "flag"]
        cube = Cube("contracts",
                          dimension_links=links,
                          measures=self.measures)
        cube.link_dimensions(dims)
        self.assertEqual(len(cube.dimensions), 3)
        self.assertIsInstance(cube.dimension("flag"), Dimension)

    @unittest.skip("requires revision")
    def test_link_hierarchies(self):
        dims = dict((d.name, d) for d in self.dimensions)

        links = [{"name": "date"}]
        cube = Cube("contracts",
                          dimension_links=links,
                          measures=self.measures)
        cube.link_dimensions(dims)
        dim = cube.dimension("date")
        self.assertEqual(len(dim.hierarchies), 2)
        self.assertEqual(dim.hierarchy().name, "ymd")

        links = [{"name": "date", "nonadditive":None}]
        cube = Cube("contracts",
                          dimension_links=links,
                          measures=self.measures)
        cube.link_dimensions(dims)
        dim = cube.dimension("date")
        self.assertEqual(len(dim.hierarchies), 2)
        self.assertEqual(dim.hierarchy().name, "ymd")

        links = [{"name": "date", "hierarchies": ["ym"]}]
        cube = Cube("contracts",
                          dimension_links=links,
                          measures=self.measures)
        cube.link_dimensions(dims)
        dim = cube.dimension("date")
        self.assertEqual(len(dim.hierarchies), 1)
        self.assertEqual(dim.hierarchy().name, "ym")

    def test_inherit_nonadditive(self):
        dims = [DIM_DATE_DESC, DIM_PRODUCT_DESC, DIM_FLAG_DESC]

        cube = {
            "name": "contracts",
            "dimensions": ["date", "product"],
            "nonadditive": "time",
            "measures": ["amount", "discount"]
        }

        dims = [Dimension.from_metadata(md) for md in dims]
        dims = dict((dim.name, dim) for dim in dims)

        cube = Cube.from_metadata(cube)

        measures = cube.measures
        self.assertEqual(measures[0].nonadditive, "time")


class ReadModelDescriptionTestCase(ModelTestCaseBase):
    def setUp(self):
        super(ReadModelDescriptionTestCase, self).setUp()

    def test_from_file(self):
        path = self.model_path("model.json")
        desc = read_model_metadata(path)

        self.assertIsInstance(desc, dict)
        self.assertTrue("cubes" in desc)
        self.assertTrue("dimensions" in desc)
        self.assertEqual(1, len(desc["cubes"]))
        self.assertEqual(6, len(desc["dimensions"]))

    def test_from_bundle(self):
        path = self.model_path("test.cubesmodel")
        desc = read_model_metadata(path)

        self.assertIsInstance(desc, dict)
        self.assertTrue("cubes" in desc)
        self.assertTrue("dimensions" in desc)
        self.assertEqual(1, len(desc["cubes"]))
        self.assertEqual(6, len(desc["dimensions"]))

        with self.assertRaises(ArgumentError):
            path = self.model_path("model.json")
            desc = read_model_metadata_bundle(path)

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
