# -*- encoding: utf-8 -*-

from __future__ import absolute_import

from collections import OrderedDict

from .. import compat
from ..errors import NoSuchAttributeError, ModelError

from .attributes import Attribute
from .base import ModelObjectBase
from .utils import object_dict, cached_property

__all__ = (
    'Dimension',
    'Level',
)


class Level(ModelObjectBase):
    """Object representing a dimension's level. Holds all level attributes.
    This object is immutable.

    * `name`: level name
    * `attributes`: list of all level attributes. Raises `ModelError` when
      `attribute` list is empty.
    * `key`: name of level key attribute (for example: ``customer_number`` for
      customer level, ``region_code`` for region level, ``month`` for month
      level).  key will be used as a grouping field for aggregations. Key
      should be unique within level. If not specified, then the first
      attribute is used as key.
    * `order`: ordering of the level. `asc` for ascending, `desc` for
      descending or might be unspecified.
    * `order_attribute`: name of attribute that is going to be used for
      sorting, default is first attribute (usually key)
    * `info`: custom information dictionary, might be used to store
      application/front-end specific information

    Note: the `attributes` are going to be owned by the `dimension`.
    """

    attribute_cls = Attribute

    @classmethod
    def expand_model(cls, model_data):
        """Returns a level description as a dictionary."""

        if isinstance(model_data, compat.string_type):
            model_data = {'name': model_data, 'attributes': [model_data]}
        else:
            model_data = dict(model_data)

        try:
            name = model_data['name']
        except KeyError:
            raise ModelError('Level has no name')

        attributes = model_data.get('attributes')
        if not attributes:
            attributes = [{'name': name}]

        model_data['attributes'] = [
            Attribute.expand_model(a) for a in attributes
        ]

        return model_data

    @classmethod
    def load(cls, model_data):
        """Create a level object from model."""

        model_data = cls.expand_model(model_data)

        try:
            name = model_data.pop('name')
        except KeyError:
            raise ModelError('No name specified in level model')

        attributes = cls.attribute_cls.load_list(model_data.pop('attributes', []))
        for attr in attributes:
            attr.validate()

        level = cls(name=name, attributes=attributes, **model_data)
        level.validate()
        return level

    def __init__(
        self, name, attributes, info=None,
        key=None, order_attribute=None, order=None,
    ):
        super(Level, self).__init__(name, ref=None, info=info)

        self.order = order
        self.attributes = attributes

        if key:
            self.key = self.get_attribute(key)
        elif len(self.attributes) >= 1:
            self.key = self.attributes[0]
        else:
            raise ModelError('Attribute list should not be empty')

        if order_attribute:
            try:
                self.order_attribute = self.get_attribute(order_attribute)
            except NoSuchAttributeError:
                raise NoSuchAttributeError(
                    'Unknown order attribute "{}" in level "{}"'
                    .format(order_attribute, self.name)
                )
        else:
            self.order_attribute = self.attributes[0]

    def __eq__(self, other):
        if not super(Level, self).__eq__(other):
            return False

        return (
            self.key == other.key and
            self.order == other.order and
            self.order_attribute == other.order_attribute and
            self.attributes == other.attributes
        )

    def all_attribute(self):
        return self.attributes

    def get_attribute(self, name):
        """Get attribute by `name`"""

        attrs = [attr for attr in self.attributes if attr.name == name]

        if attrs:
            return attrs[0]
        else:
            raise NoSuchAttributeError(name)

    def to_dict(self, full_attribute_names=False, **options):
        d = super(Level, self).to_dict(**options)

        if full_attribute_names:
            d['key'] = self.key.name
            d['order_attribute'] = self.order_attribute.name
        else:
            d['key'] = self.key.base_name
            d['order_attribute'] = self.order_attribute.base_name

        d['order'] = self.order
        d['attributes'] = [attr.to_dict(**options) for attr in self.attributes]

        return d

    def validate(self):
        if not self.attributes:
            raise ModelError(
                'Attribute list should not be empty in level "{}"'
                .format(self.name),
            )


class Dimension(ModelObjectBase):
    level_cls = Level

    @classmethod
    def expand_model(cls, model_data):
        """
        Expands `model_data` to be as complete as possible dimension model.
        """

        if isinstance(model_data, compat.string_type):
            model_data = {
                'name': model_data,
                'levels': [model_data],
                'is_plain': True,
            }
        else:
            model_data = dict(model_data)

        if not 'name' in model_data:
            raise ModelError('Dimension has no name')

        name = model_data['name']

        # Fix levels
        levels = model_data.get('levels', [])
        if not levels:
            # Default: if no attributes, then there is single flat attribute
            # whith same name as the dimension
            level = {'name': name}

            for attr in ('attributes', 'key', 'order_attribute', 'order'):
                if attr in model_data:
                    level[attr] = model_data[attr]

            levels = [level]

        if levels:
            levels = [Level.expand_model(level) for level in levels]
            model_data['levels'] = levels

        return model_data

    @classmethod
    def load(cls, model_data):
        """Create a dimension from a `model` dictionary.  Some rules:

        * ``levels`` might contain level names as strings - names of levels to
          inherit from the template
        """

        model_data = cls.expand_model(model_data)

        name = model_data.get('name')
        ref = model_data.get('ref')
        info = model_data.get('info', {})
        role = model_data.get('role')
        is_plain = model_data.get('is_plain', False)
        default_level_name = model_data.get('default_level_name', 'default')

        levels = cls.level_cls.load_list(model_data['levels'])

        dimension = cls(
            name=name,
            ref=ref,
            info=info,
            levels=levels,
            default_level_name=default_level_name,
            role=role,
            is_plain=is_plain,
        )

        for level in levels:
            for attr in level.attributes:
                attr.dimension = dimension

        dimension.validate()

        return dimension

    def __init__(
        self, name, ref=None, info=None,
        levels=None, default_level_name=None, role=None,
        is_plain=None,
    ):
        """
        * `name`: dimension name
        * `levels`: list of dimension levels (see: :class:`cubes_lite.Level`)
        * `default_level_name`: name of a level that will be used when
          no level is explicitly specified
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information (icon, color, ...)
        * `role` - one of recognized special dimension types. Currently
          supported is only ``time``.
        """

        if not ref:
            ref = name

        super(Dimension, self).__init__(name, ref, info)

        self.role = role
        self.is_plain = is_plain

        self._attributes = None
        self._default_level = None
        self._levels = None
        self.levels = levels

        level = self.get_level(default_level_name, raise_on_error=False)
        if not level:
            level = self.levels[0]

        self._default_level = level
        self.default_level_name = level.name

    def __eq__(self, other):
        if not super(Dimension, self).__eq__(other):
            return False

        return (
            self.role == other.role and
            self.default_level_name == other.default_level_name and
            self._levels == other._levels
        )

    @property
    def levels(self):
        return list(self._levels.values())

    @levels.setter
    def levels(self, levels):
        self._levels = object_dict(levels)

        # Collect attributes
        self._attributes = OrderedDict()
        for level in self.levels:
            for a in level.attributes:
                if a.dimension is not None and a.dimension is not self:
                    raise ModelError(
                        'Dimension "{}" can not claim attribute "{}" '
                        'because it is owned by another dimension: "{}"'
                        .format(self.name, a.name, a.dimension.name)
                    )

                # Own the attribute
                a.dimension = self
                self._attributes[a.name] = a

    def get_level(self, obj, raise_on_error=True):
        if not obj:
            return self._default_level

        if isinstance(obj, Level):
            return obj

        if isinstance(obj, compat.string_type):
            if obj not in self._levels:
                if not raise_on_error:
                    return None

                raise KeyError(
                    'No level "{}" in dimension "{}"'.format(obj, self.name)
                )
            return self._levels[obj]

        if raise_on_error:
            raise ValueError(
                'Unknown level object "{}" (should be a string or Level)'
                .format(obj)
            )
        else:
            return None

    @cached_property
    def all_attributes(self):
        return list(self._attributes.values())

    def get_attribute(self, name, raise_on_error=True):
        key = '{}.{}'.format(self.name, name)

        try:
            return self._attributes[key]
        except KeyError:
            if not raise_on_error:
                return None

            raise NoSuchAttributeError(
                'Unknown attribute "{}" in dimension "{}"'.format(name, self.name),
                 name
            )

    @property
    def is_flat(self):
        return len(self.levels) == 1

    def to_dict(self, **options):
        d = super(Dimension, self).to_dict(**options)

        d['default_level_name'] = self.default_level_name

        d['role'] = self.role
        d['is_plain'] = self.is_plain

        d['levels'] = [level.to_dict(**options) for level in self.levels]

        return d

    def validate(self):
        if not self.levels:
            raise ModelError(
                'No levels in dimension "{}"'.format(self.name)
            )

        if (
            self.default_level_name and
            not self.get_level(self.default_level_name, raise_on_error=False)
        ):
            raise ModelError(
                'Default level "{}" does not exist in dimension "{}"'
                .format(self.default_level_name, self.name),
            )

        for level_name, level in self._levels.items():
            if not level.attributes:
                raise ModelError(
                    'Level "{}" in dimension "{}" has no '
                    'attributes'.format(level.name, self.name),
                )

            if level.attributes and level.key:
                if level.key.name not in [a.name for a in level.attributes]:
                    raise ModelError(
                        'Key "{}" in level "{}" in dimension '
                        '"{}" is not in level\'s attribute list'
                        .format(level.key, level.name, self.name),
                    )

            for attribute in level.attributes:
                if not isinstance(attribute, Attribute):
                    raise ModelError(
                        'Attribute "{}" in dimension "{}" is '
                        'not instance of Attribute'
                        .format(attribute, self.name),
                    )

                if attribute.dimension is not self:
                    raise ModelError(
                        'Dimension "{}" of attribute "{}" does '
                        'not match with owning dimension "{}"'
                        .format(attribute.dimension, attribute, self.name),
                    )
