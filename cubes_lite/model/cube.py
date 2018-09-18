# -*- encoding: utf-8 -*-

from __future__ import absolute_import

from itertools import chain

from cubes_lite import compat
from cubes_lite.errors import (
    NoSuchAttributeError, NoSuchDimensionError, ModelError, ArgumentError
)

from .base import ModelObjectBase
from .utils import (
    object_dict, assert_all_instances, ensure_list, cached_property
)
from .logic import depsort_attributes
from .attributes import Measure, Aggregate, AttributeBase
from .dimension import Dimension

__all__ = (
    'Cube',
    'Model',
)


class Cube(ModelObjectBase):
    """Logical representation of a cube.

    Properties:

    * `name`: cube name, used as identifier
    * `measures`: list of measures - numerical attributes
      aggregation functions or natively aggregated values
    * `info` - custom information dictionary, might be used to store
      application/front-end specific information
    * `dimensions` - list of dimensions

    Physical properties of the cube are described in the following
    attributes. They are used by the backends:

    * `mappings` - backend-specific logical to physical mapping
      dictionary. Keys and values of this dictionary are interpreted by
      the backend.
    * `joins` - backend-specific join specification (list of dictionaries).
    """

    dimension_cls = Dimension
    measure_cls = Measure
    aggregate_cls = Aggregate

    @classmethod
    def expand_model(cls, model_data):
        """Expands `model_data` to be as complete as possible cube model."""

        model_data = dict(model_data)

        if not 'name' in model_data:
            raise ModelError('Cube has no name')

        dimensions = model_data.get('dimensions') or []
        dimensions = ensure_list(dimensions)
        dimensions = [Dimension.expand_model(d) for d in dimensions]
        model_data['dimensions'] = dimensions

        measures = model_data.get('measures') or []
        measures = ensure_list(measures)
        measures = [Measure.expand_model(m) for m in measures]
        model_data['measures'] = measures

        aggregates = model_data.get('aggregates') or []
        aggregates = ensure_list(aggregates)
        aggregates = [Aggregate.expand_model(a) for a in aggregates]
        model_data['aggregates'] = aggregates

        return model_data

    @classmethod
    def load(cls, model_data):
        model_data = cls.expand_model(model_data)

        dimensions = cls.dimension_cls.load_list(model_data.pop('dimensions'))
        measures = cls.measure_cls.load_list(model_data.pop('measures'))
        aggregates = cls.aggregate_cls.load_list(model_data.pop('aggregates'))

        for obj in chain(dimensions, measures, aggregates):
            obj.validate()

        cube = cls(
            measures=measures,
            aggregates=aggregates,
            dimensions=dimensions,
            **model_data
        )
        cube.validate()
        return cube

    def __init__(
        self, name, ref=None, info=None,
        dimensions=None, measures=None, aggregates=None,
        mappings=None, joins=None,
        browser_options=None,
        **options
    ):
        super(Cube, self).__init__(name, ref, info)

        self.mappings = mappings or []
        self.joins = joins or []
        self.browser_options = browser_options or {}
        self.browser = options.get('browser')

        assert_all_instances(dimensions, Dimension, 'dimension')
        self._dimensions = object_dict(
            dimensions,
            error_message='Duplicate dimension {key} in cube {cube}',
            error_dict={'cube': self.name},
        )

        assert_all_instances(measures, Measure, 'measure')
        self._measures = object_dict(
            measures,
            error_message='Duplicate measure {key} in cube {cube}',
            error_dict={'cube': self.name},
        )

        assert_all_instances(aggregates, Aggregate, 'aggregate')
        self._aggregates = object_dict(
            aggregates,
            error_message='Duplicate aggregate {key} in cube {cube}',
            error_dict={'cube': self.name},
        )

        all_attributes = []
        for dimension in self.dimensions:
            all_attributes += dimension.all_attributes
        all_attributes += self.measures
        all_attributes += self.aggregates

        self._all_attributes = object_dict(
            all_attributes,
            error_message='Duplicate attribute {key} in cube {cube}',
            error_dict={'cube': self.name},
        )

    @cached_property
    def measures(self):
        return list(self._measures.values())

    def get_measure(self, name, raise_on_error=True):
        """Get measure object of `Measure` type.

        Raises `NoSuchAttributeError` when there is no such measure.
        """

        if isinstance(name, Measure):
            return name

        try:
            return self._measures[name]
        except KeyError:
            if not raise_on_error:
                return None
            raise NoSuchAttributeError(
                'Cube "{}" has no measure "{}"'.format(self.name, name)
            )

    @cached_property
    def dimensions(self):
        return list(self._dimensions.values())

    def get_dimension(self, name, raise_on_error=True):
        """Get dimension object.

        Raises `NoSuchDimensionError` when there is no such dimension.
        """

        if isinstance(name, Dimension):
            return name

        try:
            return self._dimensions[name]
        except KeyError:
            if not raise_on_error:
                return None
            raise NoSuchDimensionError(
                'Cube "{}" has no dimension "{}"'.format(self.name, name)
            )

    @cached_property
    def aggregates(self):
        return list(self._aggregates.values())

    def get_aggregate(self, name, raise_on_error=True):
        """Get aggregate object of `Aggregate` type.

        Raises `NoSuchAttributeError` when there is no such aggregate.
        """

        if isinstance(name, Aggregate):
            return name

        try:
            return self._aggregates[name]
        except KeyError:
            if not raise_on_error:
                return None
            raise NoSuchAttributeError(
                'Cube "{}" has no measure aggregate "{}"'
                .format(self.name, name)
            )

    @cached_property
    def all_attributes(self):
        return list(self._all_attributes.values())

    @cached_property
    def all_fact_attributes(self):
        """All cube's attributes from the fact: attributes of dimensions,
        details and measures."""

        attributes = []
        for dimension in self.dimensions:
            attributes += dimension.all_attributes

        attributes += self.measures

        return attributes

    @cached_property
    def all_aggregate_attributes(self):
        """All cube's attributes for aggregation: attributes of dimensions and
        aggregates."""

        attributes = []
        for dimension in self.dimensions:
            attributes += dimension.attributes

        attributes += self.aggregates

        return attributes

    def get_attributes(self, attributes, raise_on_error=True):
        """Returns a list of cube's attributes."""

        result = set()
        for name in attributes:
            if isinstance(name, AttributeBase):
                result.add(name)
                continue

            if not isinstance(name, compat.string_type):
                name = str(name)

            try:
                attr = self._all_attributes[name]
            except KeyError:
                if not raise_on_error:
                    continue
                raise NoSuchAttributeError(
                    'Unknown attribute "{}" in cube "{}"'
                    .format(name, self.name)
                )
            result.add(attr)

        return list(result)

    def collect_dependencies(self, attributes):
        """Collect all original and dependant cube attributes for
        `attributes`, sorted by their dependency: starting with attributes
        that don't depend on anything. For example, if the `attributes` is [a,
        b] and a = c * 2, then the result list would be [b, c, a] or [c, b,
        a].
        """

        attributes = self.get_attributes(attributes)
        if not attributes:
            return []

        all_dependencies = {
            attr: self.get_attributes(attr.dependencies)
            for attr in self.all_attributes
        }

        return depsort_attributes(attributes, all_dependencies)

    def to_dict(self, with_mappings=True, **options):
        """Convert to a dictionary. If `with_mappings` is ``True`` (which is
        default) then `joins`, `mappings` and `browser_options` are included.
        """

        d = super(Cube, self).to_dict(**options)

        d['aggregates'] = [m.to_dict(**options) for m in self.aggregates]
        d['measures'] = [m.to_dict(**options) for m in self.measures]
        d['dimensions'] = [dim.to_dict(**options) for dim in self.dimensions]

        if with_mappings:
            d['mappings'] = self.mappings
            d['joins'] = self.joins
            d['browser_options'] = self.browser_options

        return d

    def __eq__(self, other):
        if not super(Cube, self).__eq__(other):
            return False

        return (
            self.dimensions == other.dimensions and
            self.measures == other.measures and
            self.aggregates == other.aggregates and
            self.mappings == other.mappings and
            self.joins == other.joins and
            self.browser_options == other.browser_options
        )

    def validate(self):
        valid_names = {
            attr.name
            for attr in self.all_attributes
        }
        for aggregate in self.aggregates:
            if aggregate.depends_on:
                for dependant in aggregate.depends_on:
                    if dependant not in valid_names:
                        raise ModelError(
                            'Unknown dependency "{}" in aggregate "{}"'
                            .format(dependant, aggregate.name)
                        )


class Model(ModelObjectBase):
    """Logical representation for a set of cubes."""

    cube_cls = Cube

    @classmethod
    def expand_model(cls, model_data):
        return model_data

    @classmethod
    def load(cls, model_data):
        model_data = cls.expand_model(model_data)

        cubes = cls.cube_cls.load_list(model_data.pop('cubes'))

        mappgins = model_data.pop('mappings', {})
        joins = model_data.pop('joins', [])

        for cube in cubes:
            cube.mappings.update(mappgins)
            cube.joins.extend(joins)

        model = cls(
            cubes=cubes,
            **model_data
        )
        model.validate()
        return model

    def __init__(
        self, name, cubes, info=None,
        browser_options=None,
    ):
        super(Model, self).__init__(name, ref=None, info=info)

        self.browser_options = browser_options or {}

        assert_all_instances(cubes, Cube, 'cube')
        self._cubes = object_dict(
            cubes,
            error_message='Duplicate cube {key} in mode {model}',
            error_dict={'model': self.name},
        )

    @cached_property
    def cubes(self):
        return list(self._cubes.values())

    def get_cube(self, name):
        try:
            return self._cubes[name]
        except KeyError:
            raise NoSuchAttributeError(
                'Model "{}" has no cube "{}"'.format(self.name, name)
            )

    def get_dimension(self, name):
        for cube in self.cubes:
            dimension = cube.get_dimension(name, raise_on_error=False)
            if dimension:
                # TODO: is getting first appropriate cube correct ?
                # dimensions can be repeated in different cubes
                return dimension
        return None

    @cached_property
    def all_aggregates(self):
        result = []
        for cube in self.cubes:
            result.extend(cube.aggregates)
        return result

    def get_aggregate(self, name):
        for cube in self.cubes:
            aggregate = cube.get_aggregate(name, raise_on_error=False)
            if aggregate:
                return aggregate
        return None

    @cached_property
    def all_attributes(self):
        result = set()
        for cube in self.cubes:
            result.update(cube.all_attributes)
        return result

    def get_attributes(self, attributes):
        result = []
        for cube in self.cubes:
            attributes = cube.get_attributes(attributes, raise_on_error=False)
            for attribute in attributes:
                if attribute not in result:
                    result.append(attribute)
        return result

    def collect_dependencies(self, attributes):
        attributes = self.get_attributes(attributes)
        if not attributes:
            return []

        all_dependencies = {
            attr: self.get_attributes(attr.dependencies)
            for attr in self.all_attributes
        }

        return depsort_attributes(attributes, all_dependencies)

    def get_related_cubes(self, attributes):
        attributes = self.collect_dependencies(attributes)

        cubes = set()
        for attribute in attributes:
            if isinstance(attribute, compat.string_type):
                name = attribute
            else:
                name = attribute.name

            for cube in self.cubes:
                attribute = cube.get_attributes([name], raise_on_error=False)
                if attribute:
                    cubes.add(cube)

                    # getting only first cube, so cube order matters
                    break
            else:
                raise ArgumentError('Unknown attribute: "{}"'.format(name))

        return cubes

    def to_dict(self, **options):
        d = super(Model, self).to_dict(**options)

        d['cubes'] = [c.to_dict(**options) for c in self.cubes]

        d['browser_options'] = self.browser_options

        return d

    def validate(self):
        all_aggregates = []
        for cube in self.cubes:
            for aggregate in cube.aggregates:
                if aggregate in all_aggregates:
                    raise ModelError(
                        'Aggregate "{}" in cube "{}" is not unique in whole model'
                        .format(aggregate, cube)
                    )
                all_aggregates.append(aggregate)

        all_measures = []
        for cube in self.cubes:
            for measure in cube.measures:
                if measure in all_measures:
                    raise ModelError(
                        'Measure "{}" in cube "{}" is not unique in whole model'
                        .format(measure, cube)
                    )
                all_measures.append(measure)
