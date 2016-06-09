# -*- encoding: utf-8 -*-
"""Metadata validation
"""

from __future__ import absolute_import

import pkgutil
import json

from collections import namedtuple
from .. import compat

try:
    import jsonschema
except ImportError:
    from ..common import MissingPackage
    jsonschema = MissingPackage("jsonschema", "Model validation")

__all__ = (
    "validate_model",
)


ValidationError = namedtuple("ValidationError",
                            ["severity", "scope", "object", "property", "message"])


def validate_model(metadata):
    """Validate model metadata."""

    validator = ModelMetadataValidator(metadata)
    return validator.validate()


class ModelMetadataValidator(object):
    def __init__(self, metadata):
        self.metadata = metadata

        data = pkgutil.get_data("cubes", "schemas/model.json")
        self.model_schema = json.loads(compat.to_str(data))

        data = pkgutil.get_data("cubes", "schemas/cube.json")
        self.cube_schema = json.loads(compat.to_str(data))

        data = pkgutil.get_data("cubes", "schemas/dimension.json")
        self.dimension_schema = json.loads(compat.to_str(data))

    def validate(self):
        errors = []

        errors += self.validate_model()

        if "cubes" in self.metadata:
            for cube in self.metadata["cubes"]:
                errors += self.validate_cube(cube)

        if "dimensions" in self.metadata:
            for dim in self.metadata["dimensions"]:
                errors += self.validate_dimension(dim)

        return errors

    def _collect_errors(self, scope, obj, validator, metadata):
        errors = []

        for error in validator.iter_errors(metadata):
            if error.path:
                path = [str(item) for item in error.path]
                ref = ".".join(path)
            else:
                ref = None

            verror = ValidationError("error", scope, obj, ref, error.message)
            errors.append(verror)

        return errors

    def validate_model(self):
        validator = jsonschema.Draft4Validator(self.model_schema)
        errors = self._collect_errors("model", None, validator, self.metadata)

        dims = self.metadata.get("dimensions")
        if dims and isinstance(dims, list):
            for dim in dims:
                if isinstance(dim, compat.string_type):
                    err = ValidationError("default", "model", None,
                                          "dimensions",
                                          "Dimension '%s' is not described, "
                                          "creating flat single-attribute "
                                          "dimension" % dim)
                    errors.append(err)

        return errors

    def validate_cube(self, cube):
        validator = jsonschema.Draft4Validator(self.cube_schema)
        name = cube.get("name")

        return self._collect_errors("cube", name, validator, cube)

    def validate_dimension(self, dim):
        validator = jsonschema.Draft4Validator(self.dimension_schema)
        name = dim.get("name")

        errors = self._collect_errors("dimension", name, validator, dim)

        if "default_hierarchy_name" not in dim:
            error = ValidationError("default", "dimension", name, None,
                                    "No default hierarchy name specified, "
                                    "using first one")
            errors.append(error)

        if "levels" not in dim and "attributes" not in dim:
            error = ValidationError("default", "dimension", name, None,
                                    "Neither levels nor attributes specified, "
                                    "creating flat dimension without details")
            errors.append(error)

        elif "levels" in dim and "attributes" in dim:
            error = ValidationError("error", "dimension", name, None,
                                    "Both levels and attributes specified")
            errors.append(error)

        return errors
