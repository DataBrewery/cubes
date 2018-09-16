# -*- encoding: utf-8 -*-

from __future__ import absolute_import

import json
import os
import pkgutil

import jsonschema

from cubes_lite import compat, PACKAGE_NAME
from cubes_lite.errors import ModelError

from .cube import Model

__all__ = (
    'read_model',
)


class Reader(object):
    schemas_path = 'model/schemas'

    model_entry_file = 'model.json'
    cube_entry_file_simplified = 'cube_{name}.json'
    cube_entry_file = 'cube.json'
    dimension_entry_file = 'dim_{name}.json'

    def __init__(self, source):
        self.source = source

        path = os.path.join(self.schemas_path, 'model.json')
        data = pkgutil.get_data(PACKAGE_NAME, path)
        self.model_schema = json.loads(compat.to_str(data))

        path = os.path.join(self.schemas_path, 'cube.json')
        data = pkgutil.get_data(PACKAGE_NAME, path)
        self.cube_schema = json.loads(compat.to_str(data))

        path = os.path.join(self.schemas_path, 'dimension.json')
        data = pkgutil.get_data(PACKAGE_NAME, path)
        self.dimension_schema = json.loads(compat.to_str(data))

    @staticmethod
    def load_json(url):
        """Opens `resource` either as a file with `open()`or as URL with
        `urlopen()`. Returns opened handle."""

        parts = compat.urlparse(url)

        if parts.scheme in ('', 'file'):
            handle = compat.open_unicode(parts.path)
        elif len(parts.scheme) == 1:
            # TODO: This is temporary hack for MS Windows which can be
            # replaced by
            # proper python 3.4 functionality later
            handle = compat.open_unicode(url)
        else:
            handle = compat.urlopen(url)

        try:
            desc = json.load(handle)
        except ValueError as e:
            raise SyntaxError('Syntax error in "{}": {}'.format(url, str(e)))
        finally:
            handle.close()

        return desc

    @staticmethod
    def validate_schema(schema, data):
        validator = jsonschema.Draft4Validator(schema)

        errors = []
        for error in validator.iter_errors(data):
            if error.path:
                path = [str(item) for item in error.path]
                ref = '.'.join(path)
            else:
                ref = None

            error = (ref, error.message)
            errors.append(error)

        if errors:
            raise ModelError(
                'Mapper validation error:\n{}'
                .format('\n'.join([
                    '\t"{}": {}'.format(ref if ref else 'attr', msg)
                    for ref, msg in errors
                ]))
            )

    def read(self, source):
        """Reads a model description from `source` which can be a filename, URL,
        file-like object or a path to a directory. Returns a model
        description dictionary."""

        if not isinstance(source, compat.string_type):
            return json.load(source)

        parts = compat.urlparse(source)
        if parts.scheme in ('', 'file') and os.path.isdir(parts.path):
            source = parts.path
            return self.read_bundle(source)
        elif len(parts.scheme) == 1 and os.path.isdir(source):
            # TODO: same hack as in _json_from_url
            return self.read_bundle(source)
        else:
            return self.load_json(source)

    def read_bundle(self, path):
        """Load logical model a directory specified by `path`.  Returns a model
        description dictionary. Model directory bundle has structure:

        * ``store.model/``
            * ``model.json``
            * ``cube1/``
                * ``cube.json``
                * ``dim_*.json``
            * ``cube2/``
                * ``cube.json``
                * ``dim_*.json``
        """

        assert os.path.isdir(path), 'Path "%s" is not a directory.'

        info_path = os.path.join(path, self.model_entry_file)
        if not os.path.exists(info_path) or not os.path.isfile(info_path):
            raise ModelError(
                'Main model info "%s" does not exist'.format(info_path)
            )

        model = self.load_json(info_path)
        self.validate_schema(self.model_schema, model)

        cube_names = model['cubes']
        model['cubes'] = []
        for cube in cube_names:
            cube_path = os.path.join(path, cube)
            info_path = os.path.join(cube_path, self.cube_entry_file)

            if not os.path.exists(cube_path):
                cube_path = path
                info_path = os.path.join(
                    cube_path,
                    self.cube_entry_file_simplified.format(name=cube),
                )

            if not (os.path.exists(info_path) and os.path.isfile(info_path)):
                raise ModelError(
                    'Bad cube entry file: "{}"'.format(info_path)
                )

            cube_model = self.load_json(info_path)
            self.validate_schema(self.cube_schema, cube_model)
            model['cubes'].append(cube_model)

            dimension_names = cube_model['dimensions']
            cube_model['dimensions'] = []
            for dimension in dimension_names:
                if not isinstance(dimension, compat.string_type):
                    continue

                info_path = os.path.join(
                    cube_path,
                    self.dimension_entry_file.format(name=dimension),
                )
                if not (os.path.exists(info_path) and os.path.isfile(info_path)):
                    # plain dimension doesn't require a file description
                    dimension_model = dimension
                else:
                    dimension_model = self.load_json(info_path)
                    self.validate_schema(self.dimension_schema, dimension_model)

                cube_model['dimensions'].append(dimension_model)
            continue

        return model


def read_model(source):
    reader = Reader(source)
    model_data = reader.read(source)
    model_obj = Model.load(model_data)
    model_obj.validate()
    return model_obj
