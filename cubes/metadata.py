# -*- encoding: utf-8 -*-
"""Functions for manipulating the model metadata in it's raw form –
dictionary:

    * Model metadata loading and writing
    * Expanding metadata – resolving defaults, converting strings to required
      structures
    * Simplifying metadata – removing defaults for better output readability
    * Metadata validation

Purpose of this module is to maintain compatibility between model metadata in
the future.

"""

from __future__ import absolute_import

import pkgutil
import shutil
import json
import os
import re

from collections import OrderedDict, namedtuple
from .errors import ModelError, CubesError, ArgumentError
from .errors import ModelInconsistencyError
from . import compat

try:
    import jsonschema
except ImportError:
    from .common import MissingPackage
    jsonschema = MissingPackage("jsonschema", "Model validation")

__all__ = (
    "read_model_metadata",
    "read_model_metadata_bundle",
    "write_model_metadata_bundle",

    "expand_cube_metadata",
    "expand_dimension_links",
    "expand_dimension_metadata",
    "expand_level_metadata",
    "expand_attribute_metadata",

    "validate_model",
)

# TODO: add the following:
#
# append_mappings(cube, mappings)
# append_joins(cube, joins)
# link_mappings(cube) -> link mappings with their respective attributes
# strip_mappings(cube) -> remove mappings from cube
# strip_mappings

def _json_from_url(url):
    """Opens `resource` either as a file with `open()`or as URL with
    `urlopen()`. Returns opened handle. """

    parts = compat.urlparse(url)

    if parts.scheme in ('', 'file'):
        handle = compat.open_unicode(parts.path)
    elif len(parts.scheme) == 1:
        # TODO: This is temporary hack for MS Windows which can be replaced by
        # proper python 3.4 functionality later
        handle = compat.open_unicode(url)
    else:
        handle = compat.urlopen(url)

    try:
        desc = json.load(handle)
    except ValueError as e:
        import pdb; pdb.set_trace()
        raise SyntaxError("Syntax error in %s: %s" % (url, str(e)))
    finally:
        handle.close()

    return desc


def read_model_metadata(source):
    """Reads a model description from `source` which can be a filename, URL,
    file-like object or a path to a directory. Returns a model description
    dictionary."""

    if isinstance(source, compat.string_type):
        parts = compat.urlparse(source)
        if parts.scheme in ('', 'file') and os.path.isdir(parts.path):
            source = parts.path
            return read_model_metadata_bundle(source)
        elif len(parts.scheme) == 1 and os.path.isdir(source):
            # TODO: same hack as in _json_from_url
            return read_model_metadata_bundle(source)
        else:
            return _json_from_url(source)
    else:
        return json.load(source)


def read_model_metadata_bundle(path):
    """Load logical model a directory specified by `path`.  Returns a model
    description dictionary. Model directory bundle has structure:

    * ``model.cubesmodel/``
        * ``model.json``
        * ``dim_*.json``
        * ``cube_*.json``

    The dimensions and cubes lists in the ``model.json`` are concatenated with
    dimensions and cubes from the separate files.
    """

    if not os.path.isdir(path):
        raise ArgumentError("Path '%s' is not a directory.")

    info_path = os.path.join(path, 'model.json')

    if not os.path.exists(info_path):
        raise ModelError('main model info %s does not exist' % info_path)

    model = _json_from_url(info_path)

    # Find model object files and load them

    if not "dimensions" in model:
        model["dimensions"] = []

    if not "cubes" in model:
        model["cubes"] = []

    for dirname, dirnames, filenames in os.walk(path):
        for filename in filenames:
            if os.path.splitext(filename)[1] != '.json':
                continue

            split = re.split('_', filename)
            prefix = split[0]
            obj_path = os.path.join(dirname, filename)

            if prefix in ('dim', 'dimension'):
                desc = _json_from_url(obj_path)
                try:
                    name = desc["name"]
                except KeyError:
                    raise ModelError("Dimension file '%s' has no name key" %
                                                                     obj_path)
                if name in model["dimensions"]:
                    raise ModelError("Dimension '%s' defined multiple times " %
                                        "(in '%s')" % (name, obj_path) )
                model["dimensions"].append(desc)

            elif prefix == 'cube':
                desc = _json_from_url(obj_path)
                try:
                    name = desc["name"]
                except KeyError:
                    raise ModelError("Cube file '%s' has no name key" %
                                                                     obj_path)
                if name in model["cubes"]:
                    raise ModelError("Cube '%s' defined multiple times "
                                        "(in '%s')" % (name, obj_path) )
                model["cubes"].append(desc)

    return model


def write_model_metadata_bundle(path, metadata, replace=False):
    """Writes a model metadata bundle into new directory `target` from
    `metadata`. Directory should not exist."""

    if os.path.exists(path):
        if not os.path.isdir(path):
            raise CubesError("Target exists and is a file, "
                                "can not replace")
        elif not os.path.exists(os.path.join(path, "model.json")):
            raise CubesError("Target is not a model directory, "
                                "can not replace.")
        if replace:
            shutil.rmtree(path)
        else:
            raise CubesError("Target already exists. "
                                "Remove it or force replacement.")

    os.makedirs(path)

    metadata = dict(metadata)

    dimensions = metadata.pop("dimensions", [])
    cubes = metadata.pop("cubes", [])

    for dim in dimensions:
        name = dim["name"]
        filename = os.path.join(path, "dim_%s.json" % name)
        with open(filename, "w") as f:
            json.dump(dim, f, indent=4)

    for cube in cubes:
        name = cube["name"]
        filename = os.path.join(path, "cube_%s.json" % name)
        with open(filename, "w") as f:
            json.dump(cube, f, indent=4)

    filename = os.path.join(path, "model.json")
    with open(filename, "w") as f:
        json.dump(metadata, f, indent=4)


def expand_cube_metadata(metadata):
    """Expands `metadata` to be as complete as possible cube metadata.
    `metadata` should be a dictionary."""

    metadata = dict(metadata)

    if not "name" in metadata:
        raise ModelError("Cube has no name")

    links = metadata.get("dimensions", [])

    if links:
        links = expand_dimension_links(metadata["dimensions"])

    # TODO: depreciate this
    if "hierarchies" in metadata:
        dim_hiers = dict(metadata["hierarchies"])

        for link in links:
            try:
                hiers = dim_hiers.pop(link["name"])
            except KeyError:
                continue

            link["hierarchies"] = hiers

        if dim_hiers:
            raise ModelError("There are hierarchies specified for non-linked "
                             "dimensions: %s." % (dim_hiers.keys()))

    nonadditive = metadata.pop("nonadditive", None)
    if "measures" in metadata:
        measures = []
        for attr in metadata["measures"]:
            attr = expand_attribute_metadata(attr)
            if nonadditive:
                attr["nonadditive"] = attr.get("nonadditive", nonadditive)
            measures.append(attr)

        metadata["measures"] = measures

    # Replace the dimensions
    if links:
        metadata["dimensions"] = links

    return metadata


def expand_dimension_links(metadata):
    """Expands links to dimensions. `metadata` should be a list of strings or
    dictionaries (might be mixed). Returns a list of dictionaries with at
    least one key `name`. Other keys are: `hierarchies`,
    `default_hierarchy_name`, `nonadditive`, `cardinality`, `template`"""

    links = []

    for link in metadata:
        if isinstance(link, compat.string_type):
            link = {"name": link}
        elif "name" not in link:
            raise ModelError("Dimension link has no name")

        links.append(link)

    return links


def expand_dimension_metadata(metadata, expand_levels=False):
    """
    Expands `metadata` to be as complete as possible dimension metadata. If
    `expand_levels` is `True` then levels metadata are expanded as well.
    """

    if isinstance(metadata, compat.string_type):
        metadata = {"name":metadata, "levels": [metadata]}
    else:
        metadata = dict(metadata)

    if not "name" in metadata:
        raise ModelError("Dimension has no name")

    name = metadata["name"]

    # Fix levels
    levels = metadata.get("levels", [])
    if not levels and expand_levels:
        attributes = ["attributes", "key", "order_attribute", "order",
                      "label_attribute"]
        level = {}
        for attr in attributes:
            if attr in metadata:
                level[attr] = metadata[attr]

        level["cardinality"] = metadata.get("cardinality")

        # Default: if no attributes, then there is single flat attribute
        # whith same name as the dimension
        level["name"] = name
        level["label"] = metadata.get("label")

        levels = [level]

    if levels:
        levels = [expand_level_metadata(level) for level in levels]
        metadata["levels"] = levels

    # Fix hierarchies
    if "hierarchy" in metadata and "hierarchies" in metadata:
        raise ModelInconsistencyError("Both 'hierarchy' and 'hierarchies'"
                                      " specified. Use only one")

    hierarchy = metadata.get("hierarchy")
    if hierarchy:
        hierarchies = [{"name": "default", "levels": hierarchy}]
    else:
        hierarchies = metadata.get("hierarchies")

    if hierarchies:
        metadata["hierarchies"] = hierarchies

    return metadata


def expand_hierarchy_metadata(metadata):
    """Returns a hierarchy metadata as a dictionary. Makes sure that required
    properties are present. Raises exception on missing values."""

    try:
        name = metadata["name"]
    except KeyError:
        raise ModelError("Hierarchy has no name")

    if not "levels" in metadata:
        raise ModelError("Hierarchy '%s' has no levels" % name)

    return metadata

def expand_level_metadata(metadata):
    """Returns a level description as a dictionary. If provided as string,
    then it is going to be used as level name and as its only attribute. If a
    dictionary is provided and has no attributes, then level will contain only
    attribute with the same name as the level name."""
    if isinstance(metadata, compat.string_type):
        metadata = {"name":metadata, "attributes": [metadata]}
    else:
        metadata = dict(metadata)

    try:
        name = metadata["name"]
    except KeyError:
        raise ModelError("Level has no name")

    attributes = metadata.get("attributes")

    if not attributes:
        attribute = {
            "name": name,
            "label": metadata.get("label")
        }

        attributes = [attribute]

    metadata["attributes"] = [expand_attribute_metadata(a) for a in attributes]

    # TODO: Backward compatibility – depreciate later
    if "cardinality" not in metadata:
        info = metadata.get("info", {})
        if "high_cardinality" in info:
            metadata["cardinality"] = "high"

    return metadata


def expand_attribute_metadata(metadata):
    """Fixes metadata of an attribute. If `metadata` is a string it will be
    converted into a dictionary with key `"name"` set to the string value."""
    if isinstance(metadata, compat.string_type):
        metadata = {"name": metadata}

    return metadata


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
