# -*- encoding: utf-8 -*-

from __future__ import absolute_import

from collections import OrderedDict

from .. import compat
from ..errors import ModelError

from .utils import ensure_list

__all__ = (
    'ModelObjectBase',
)


class ModelObjectBase(object):
    @classmethod
    def expand_model(cls, model_data):
        if isinstance(model_data, compat.string_type):
            model_data = {'name': model_data}

        return model_data

    @classmethod
    def load(cls, model_data):
        """Create an object from `model_data` which can be a dictionary or a
        string representing the attribute name.
        """

        model_data = cls.expand_model(model_data)

        if 'name' not in model_data:
            raise ModelError(
                'Model objects model require at least name to be present.'
            )

        return cls(**model_data)

    @classmethod
    def load_list(cls, model_data_list):
        model_data_list = ensure_list(model_data_list)

        return [cls.load(model_data) for model_data in model_data_list]

    def __init__(self, name, ref=None, info=None):
        if info is not None:
            assert isinstance(info, dict)

        self.name = name
        self.ref = ref
        self.info = info or {}

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<{}: name="{}"{}>'.format(
            self.__class__.__name__,
            self.name,
            ', ref="{}"'.format(self.ref) if self.ref else '',
        )

    def __eq__(self, other):
        if not isinstance(other, ModelObjectBase):
            return False

        if type(self) is not type(other):
            return False

        return (
            self.name == other.name and
            self.ref == other.ref
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.name)

    def to_dict(self, **options):
        out = OrderedDict()

        out['name'] = self.name

        if self.ref != self.name:
            out['ref'] = self.ref

        if self.info:
            out['info'] = self.info

        return out

    def validate(self):
        pass
