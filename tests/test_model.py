# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import copy
import os
import unittest

from cubes_lite.errors import NoSuchAttributeError, NoSuchDimensionError
from cubes_lite.errors import ModelError
from cubes_lite.model import (
    read_model,
    Level, Attribute, Measure, Aggregate, Dimension, Cube, Model,
)

from .common import TESTS_PATH, CubesTestCaseBase


DIM_DATE_DESC = {
    'name': 'date',
    'levels': [
        {'name': 'year'},
        {'name': 'month', 'attributes': ['month', 'month_name']},
        {'name': 'day'}
    ]
}

DIM_FLAG_DESC = 'flag'

DIM_PRODUCT_DESC = {
    'name': 'product',
    'levels': [
        {'name': 'category', 'attributes': ['key', 'name']},
        {'name': 'subcategory', 'attributes': ['key', 'name']},
        {'name': 'product', 'attributes': ['key', 'name', 'description']}
    ]
}


class AttributeTestCase(unittest.TestCase):
    def test_basics(self):
        attr = Attribute('foo')
        self.assertEqual('foo', attr.name)
        self.assertEqual('foo', str(attr))
        self.assertEqual('foo', attr.ref)

    def test_simplify(self):
        level = Level('name', attributes=[Attribute('name')])
        dim = Dimension('group', ref='_group', levels=[level])

        attr = dim.get_attribute('name')
        self.assertEqual('group.name', attr.name)
        self.assertEqual('_group.name', attr.ref)

        self.assertEqual('group', str(dim))

        level = Level('name', attributes=[Attribute('key'), Attribute('name')])
        dim = Dimension('group', levels=[level])
        attr = dim.get_attribute('name')
        self.assertEqual('name', attr.base_name)
        self.assertEqual('group.name', attr.name)
        self.assertEqual('group.name', str(attr))
        self.assertEqual('group.name', attr.ref)

    def test_create_attribute(self):
        level = Level('name', attributes=[Attribute('key'), Attribute('name')])
        dim = Dimension('group', levels=[level])

        obj = Attribute.load('name')
        self.assertIsInstance(obj, Attribute)
        self.assertEqual('name', obj.name)

        obj = Attribute.load({'name': 'key'})
        obj.dimension = dim
        self.assertIsInstance(obj, Attribute)
        self.assertEqual('key', obj.base_name)
        self.assertEqual('group.key', obj.name)
        self.assertEqual(dim, obj.dimension)

        obj = dim.get_attribute('key')
        obj.dimension = dim
        self.assertIsInstance(obj, Attribute)
        self.assertEqual('key', obj.base_name)
        self.assertEqual('group.key', obj.name)


class MeasuresTestsCase(CubesTestCaseBase):
    def setUp(self):
        super(MeasuresTestsCase, self).setUp()
        self.metadata = self.model_metadata('measures.json')

        self.cubes_md = {}

        for cube in self.metadata['cubes']:
            self.cubes_md[cube['name']] = cube

    def cube(self, name):
        """Create a cube object `name` from measures test model."""
        return Cube.load(self.cubes_md[name])

    def test_basic(self):
        md = {}
        with self.assertRaises(ModelError):
            measure = Measure.load(md)

        measure = Measure.load('amount')
        self.assertIsInstance(measure, Measure)
        self.assertEqual('amount', measure.name)

        md = {'name': 'amount'}
        measure = Measure.load(md)
        self.assertEqual('amount', measure.name)

    def test_copy(self):
        md = {'name': 'amount'}
        measure = Measure.load(md)
        measure2 = copy.deepcopy(measure)
        self.assertEqual(measure, measure2)

    def test_aggregate(self):
        md = {}
        with self.assertRaises(ModelError):
            measure = Aggregate.load(md)

        aggregate = Aggregate.load('amount_sum')
        self.assertIsInstance(aggregate, Aggregate)
        self.assertEqual('amount_sum', aggregate.name)

    def test_fact_count(self):
        md = {'name': 'count', 'function': 'count'}
        agg = Aggregate.load(md)

        self.assertEqual('count', agg.name)
        self.assertFalse(agg.depends_on)
        self.assertEqual('count', agg.function)

    def test_fact_count2(self):
        cube = self.cube('fact_count')
        measures = cube.measures
        self.assertEqual(0, len(measures))

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual('total_events', aggregates[0].name)
        self.assertFalse(aggregates[0].depends_on)

    def test_amount_sum(self):
        cube = self.cube('amount_sum')
        measures = cube.measures
        self.assertEqual(1, len(measures))
        self.assertEqual('amount', measures[0].name)
        self.assertFalse(measures[0].depends_on)

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual('amount_sum', aggregates[0].name)
        self.assertEqual('sum', aggregates[0].function)
        self.assertEqual(['amount'], aggregates[0].depends_on)

    def test_explicit_implicit_combined(self):
        cube = self.cube('amount_sum_combined')
        measures = cube.measures
        self.assertEqual(1, len(measures))
        self.assertEqual('amount', measures[0].name)

        aggregates = cube.aggregates
        self.assertEqual(1, len(aggregates))
        self.assertEqual('total', aggregates[0].name)

    def test_measure_expression(self):
        cube = self.cube('measure_expression')
        measures = cube.measures
        self.assertEqual(3, len(measures))

        self.assertEqual('price', measures[0].name)
        self.assertEqual('costs', measures[1].name)
        self.assertEqual('revenue', measures[2].name)
        self.assertEqual(['price', 'costs'], measures[2].depends_on)

        aggregates = cube.aggregates
        self.assertEqual(0, len(aggregates))

    def test_explicit(self):
        cube = self.cube('explicit_aggregates')
        aggregates = [a.name for a in cube.aggregates]
        self.assertSequenceEqual(['amount_sum',
                                  'amount_wma',
                                  'count',
                                  ],
                                  aggregates)

    def test_explicit_conflict(self):
        with self.assertRaisesRegex(ModelError, 'Unknown dependency'):
            cube = self.cube('explicit_aggregates_conflict')


class LevelTestCase(unittest.TestCase):
    def test_initialization(self):
        self.assertRaises(ModelError, Level, 'month', [])

    def test_operators(self):
        attrs = [Attribute('foo')]
        self.assertEqual('date', str(Level('date', attrs)))

    def test_create(self):
        desc = 'year'
        level = Level.load(desc)
        self.assertIsInstance(level, Level)
        self.assertEqual('year', level.name)
        self.assertEqual(['year'], [str(a) for a in level.attributes])

        # Test default: Attributes
        desc = {'name': 'year'}
        level = Level.load(desc)
        self.assertIsInstance(level, Level)
        self.assertEqual('year', level.name)
        self.assertEqual(['year'], [str(a) for a in level.attributes])

        # Test default: Attributes
        desc = {'name': 'year', 'attributes': ['key']}
        level = Level.load(desc)
        self.assertIsInstance(level, Level)
        self.assertEqual('year', level.name)
        self.assertEqual(['key'], [str(a) for a in level.attributes])

        desc = {'name': 'year', 'attributes': ['key', 'label']}
        level = Level.load(desc)
        self.assertEqual(['key', 'label'], [str(a) for a in level.attributes])

        # Level from description with full details
        desc = {
            'name': 'month',
            'attributes': [
                {'name': 'month'},
                {'name': 'month_name'},
                {'name': 'month_sname'}
            ]
        }

        level = Level.load(desc)
        self.assertEqual(3, len(level.attributes))
        names = [str(a) for a in level.attributes]
        self.assertEqual(['month', 'month_name', 'month_sname'], names)

    def test_key_label_attributes(self):
        attrs = [Attribute('code')]
        level = Level('product', attrs)
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual('code', str(level.key))

        attrs = [Attribute('code'), Attribute('name')]
        level = Level('product', attrs)
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual('code', str(level.key))

        attrs = [Attribute('info'), Attribute('code'), Attribute('name')]
        level = Level('product', attrs, key='code')
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual('code', str(level.key))

        # Test key/label in full desc
        desc = {
            'name': 'product',
            'attributes': ['info', 'code', 'name'],
            'key': 'code'
        }

        level = Level.load(desc)
        self.assertIsInstance(level.key, Attribute)
        self.assertEqual('code', str(level.key))

    def test_level_inherit(self):
        desc = {
            'name': 'product_type',
        }

        level = Level.load(desc)
        self.assertEqual(1, len(level.attributes))

        attr = level.attributes[0]
        self.assertEqual('product_type', attr.name)

    def test_comparison(self):
        attrs = [Attribute('info'), Attribute('code'), Attribute('name')]
        level1 = Level('product', attrs, key='code')
        level2 = Level('product', attrs, key='code')
        level3 = Level('product', attrs)
        attrs = [Attribute('month'), Attribute('month_name')]
        level4 = Level('product', attrs)

        self.assertEqual(level1, level2)
        self.assertNotEqual(level2, level3)
        self.assertNotEqual(level2, level4)


class DimensionTestCase(unittest.TestCase):
    def setUp(self):
        self.levels = [
            Level('year', attributes=Attribute.load_list(['year'])),
            Level('month', attributes=Attribute.load_list(['month', 'month_name', 'month_sname'])),
            Level('day', attributes=Attribute.load_list(['day'])),
            Level('week', attributes=Attribute.load_list(['week'])),
        ]
        self.level_names = [level.name for level in self.levels]
        self.dimension = Dimension('date', levels=self.levels)

    def test_create(self):
        dim = Dimension.load('year')
        self.assertIsInstance(dim, Dimension)
        self.assertEqual('year', dim.name)
        self.assertEqual(['year'], [str(a) for a in dim.all_attributes])

        # Test default: explicit level attributes
        desc = {'name': 'date', 'levels': ['year']}
        dim = Dimension.load(desc)
        self.assertTrue(dim.is_flat)
        self.assertIsInstance(dim, Dimension)
        self.assertEqual('date', dim.name)

        self.assertEqual(['date.year'], [str(a) for a in dim.all_attributes])

        desc = {'name': 'date', 'levels': ['year', 'month', 'day']}
        dim = Dimension.load(desc)
        self.assertIsInstance(dim, Dimension)
        self.assertEqual('date', dim.name)
        refs = [str(a) for a in dim.all_attributes]
        self.assertEqual(['date.year', 'date.month', 'date.day'], refs)
        self.assertFalse(dim.is_flat)
        self.assertEqual(3, len(dim.levels))
        for level in dim.levels:
            self.assertIsInstance(level, Level)

        # Test default: implicit single level attributes
        desc = {'name': 'product', 'attributes': ['code', 'name']}
        dim = Dimension.load(desc)
        refs = [str(a) for a in dim.all_attributes]
        self.assertEqual(['product.code', 'product.name'], refs)
        self.assertEqual(1, len(dim.levels))

    def test_flat_dimension(self):
        dim = Dimension.load('foo')
        self.assertTrue(dim.is_flat)
        self.assertEqual(1, len(dim.levels))

        level = dim.get_level('foo')
        self.assertIsInstance(level, Level)
        self.assertEqual('foo', level.name)
        self.assertEqual(1, len(level.attributes))
        self.assertEqual('foo', str(level.key))

        attr = level.attributes[0]
        self.assertIsInstance(attr, Attribute)
        self.assertEqual('foo', attr.name)

    def test_comparisons(self):
        dim1 = Dimension.load(DIM_DATE_DESC)
        dim2 = Dimension.load(DIM_DATE_DESC)

        self.assertListEqual(dim1.levels, dim2.levels)
        self.assertEqual(dim1, dim2)

    def test_to_dict(self):
        desc = self.dimension.to_dict()
        dim = Dimension.load(desc)

        self.assertEqual(self.dimension.levels, dim.levels)
        self.assertEqual(self.dimension, dim)

    def test_info(self):
        md = {
            'name': 'template',
            'levels': [
                { 'name': 'one', 'info': {'units': '$', 'format': 'foo'}}
            ]
        }
        dim = Dimension.load(md)

        level = dim.get_level('one')
        self.assertIn('units', level.info)
        self.assertIn('format', level.info)
        self.assertEqual(level.info['units'], '$')
        self.assertEqual(level.info['format'], 'foo')


class CubeTestCase(unittest.TestCase):
    def setUp(self):
        self.measures = Measure.load_list(['amount', 'discount'])

        a = [DIM_DATE_DESC, DIM_PRODUCT_DESC, DIM_FLAG_DESC]
        self.dimensions = [Dimension.load(desc) for desc in a]

        self.cube = Cube(
            'contracts',
            dimensions=self.dimensions,
            measures=self.measures,
        )

    def test_create_cube(self):
        cube = {
                'name': 'cube',
                'dimensions': ['date'],
                'aggregates': [{'name': 'record_count', 'function': 'count'}],
                'measures': []
        }
        cube = Cube.load(cube)

        self.assertEqual(cube.name, 'cube')
        self.assertEqual(len(cube.aggregates), 1)

    def test_get_dimension(self):
        self.assertListEqual(self.dimensions, self.cube.dimensions)

        self.assertEqual('date', self.cube.get_dimension('date').name)
        self.assertEqual('product', self.cube.get_dimension('product').name)
        self.assertEqual('flag', self.cube.get_dimension('flag').name)
        self.assertRaises(NoSuchDimensionError, self.cube.get_dimension, 'xxx')

    def test_get_measure(self):
        self.assertListEqual(self.measures, self.cube.measures)

        self.assertEqual('amount', self.cube.get_measure('amount').name)
        self.assertEqual('discount', self.cube.get_measure('discount').name)
        self.assertRaises(NoSuchAttributeError, self.cube.get_measure, 'xxx')

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
            'flag',
            'amount',
            'discount']
        self.assertSequenceEqual(expected, refs)

        attributes = self.cube.get_attributes(['date.year', 'product.name'])
        refs = [a.ref for a in attributes]
        expected = ['date.year', 'product.name']
        self.assertSequenceEqual(expected, refs)

        attributes = self.cube.get_attributes(['amount'])
        refs = [a.ref for a in attributes]
        self.assertSequenceEqual(['amount'], refs)

        with self.assertRaises(NoSuchAttributeError):
            self.cube.get_attributes(['UNKNOWN'])

    def test_to_dict(self):
        desc = self.cube.to_dict()
        dims = dict((dim.name, dim.to_dict()) for dim in self.dimensions)
        desc['dimensions'] = dims

        cube = Cube.load(desc)
        self.assertEqual(self.cube.dimensions, cube.dimensions)
        self.assertEqual(self.cube.measures, cube.measures)
        self.assertEqual(self.cube, cube)


class ReadModelDescriptionTestCase(CubesTestCaseBase):
    def test_from_file(self):
        path = self.model_path('model.json')
        desc = read_model(path)

        self.assertIsInstance(desc, Model)
        self.assertEqual(1, len(desc.cubes))
        self.assertEqual(6, len(desc.cubes[0].dimensions))

    def test_from_bundle(self):
        path = self.model_path('test.cubesmodel')
        desc = read_model(path)

        self.assertIsInstance(desc, Model)
        self.assertEqual(1, len(desc.cubes))
        self.assertEqual(6, len(desc.cubes[0].dimensions))
