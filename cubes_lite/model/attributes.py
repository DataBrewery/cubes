# -*- encoding: utf-8 -*-

from __future__ import absolute_import

from cubes_lite.errors import ModelError

from .base import ModelObjectBase

__all__ = (
    'Attribute',
    'Measure',
    'Aggregate',
)


class AttributeBase(ModelObjectBase):
    """Base class for dimension attributes, measures and measure
    aggregates.

    Attributes:

    * `name` - attribute name, used as identifier
    * `info` - custom information dictionary, might be used to store
      application/front-end specific information
    * `missing_value` - value to be used when there is no value (``NULL``)
      in the data source. Support of this attribute property depends on the
      backend. Please consult the backend documentation for more
      information.
    * `depends_on` - attribute dependencies: other existing attributes.

    `ArgumentError` is raised when unknown ordering type is
    specified.
    """

    def __init__(
        self, name, ref=None, info=None,
        missing_value=None, depends_on=None,
    ):
        if not ref:
            ref = name

        super(AttributeBase, self).__init__(name, ref, info)

        self.missing_value = missing_value
        self.depends_on = depends_on

    def to_dict(self, **options):
        d = super(AttributeBase, self).to_dict(**options)

        d['missing_value'] = self.missing_value
        d['depends_on'] = self.depends_on

        return d

    @property
    def is_base(self):
        return not self.depends_on

    @property
    def dependencies(self):
        """Set of attributes that the `attribute` depends on."""

        if not self.depends_on:
            return set()

        return set(self.depends_on)


class Attribute(AttributeBase):
    def __init__(
        self, name, dimension=None, info=None,
        missing_value=None, depends_on=None,
    ):
        """Dimension attribute object. Also used as fact detail.

        Attributes:

        * `name` - attribute name, used as identifier
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information
        """

        super(Attribute, self).__init__(
            name=name,
            ref=None, # ref sets from dimension
            info=info,
            missing_value=missing_value,
            depends_on=depends_on,
        )

        self.base_name = name

        self._dimension = None
        self.dimension = dimension

    @property
    def dimension(self):
        return self._dimension

    @dimension.setter
    def dimension(self, dimension):
        if not dimension:
            return

        self._dimension = dimension

        # plain dimension, without extract-transforms on column
        if dimension.name == self.base_name:
            self.ref = self.name = self.base_name
        else:
            self.ref = '{}.{}'.format(dimension.ref, self.base_name)
            self.name = '{}.{}'.format(dimension.name, self.base_name)

    def to_dict(self, with_dimension=False, **options):
        d = super(Attribute, self).to_dict(**options)

        d.pop('ref', None)
        d['name'] = self.base_name

        if with_dimension:
            d['dimension'] = self.dimension.to_dict(**options)

        return d


class Measure(AttributeBase):
    """Cube measure attribute - a numerical attribute that can be
    aggregated.

    Example1:
        {
            "name": "spend_value",
            "ref": "spend"
        }

    Example2:
        {
            "name": "revenue"
        }
    """


class Aggregate(AttributeBase):
    def __init__(
        self, name, function='count', info=None,
        missing_value=None, depends_on=None,
    ):
        """
        * `function` - aggregation function for the measure
        * `depends_on` - measures for this aggregate

        Example1:
            {
                "name": "spend_sum",
                "function": "sum"
                "depends_on": "spend",
            }

        Example2:
            {
                "name": "tap_through_rate",
                "function": "fraction",
                "depends_on": ["taps_sum", "impressions_sum"]
            }
        """

        if depends_on and not isinstance(depends_on, list):
            depends_on = [depends_on]

        super(Aggregate, self).__init__(
            name=name,
            ref=None,
            info=info,
            missing_value=missing_value,
            depends_on=depends_on,
        )

        self.function = function

    @property
    def public_name(self):
        return self.name.rstrip('_')

    def __eq__(self, other):
        if not super(Aggregate, self).__eq__(other):
            return False

        return self.function == other.function

    def __hash__(self):
        return hash(self.name)

    @property
    def is_base(self):
        return False

    def to_dict(self, **options):
        d = super(Aggregate, self).to_dict(**options)

        d['function'] = self.function

        return d

    def validate(self):
        if self.function is None:
            raise ModelError(
                'No function for aggregate: "{}"'.format(self.name)
            )

        if self.function != 'count':
            if not self.depends_on:
                raise ModelError(
                    'No dependants for aggregate: "{}"'.format(self.name)
                )
