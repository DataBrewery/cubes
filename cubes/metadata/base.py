
# -*- encoding: utf-8 -*-
"""Cube logical model"""

from __future__ import absolute_import

import json
import os
import re
import shutil

from collections import OrderedDict

from ..common import IgnoringDictionary, to_label
from ..errors import ModelError, ArgumentError, CubesError
from .. import compat

__all__ = (
    "ModelObject",
    "read_model_metadata",
    "read_model_metadata_bundle",
    "write_model_metadata_bundle",
    "object_dict",
)


class ModelObject(object):
    """Base classs for all model objects."""

    localizable_attributes = []
    localizable_lists = []

    def __init__(self, name=None, label=None, description=None, info=None):
        """Initializes model object basics. Assures that the `info` is a
        dictionary."""

        self.name = name
        self.label = label
        self.description = description
        self.info = info or {}

    def to_dict(self, create_label=None, **options):
        """Convert to a dictionary. If `with_mappings` is ``True`` (which is
        default) then `joins`, `mappings`, `fact` and `options` are included.
        Should be set to ``False`` when returning a dictionary that will be
        provided in an user interface or through server API.
        """

        out = IgnoringDictionary()

        out["name"] = self.name
        out["info"] = self.info

        if create_label:
            out["label"] = self.label or to_label(self.name)
        else:
            out["label"] = self.label

        out["description"] = self.description

        return out

    def localized(self, context):
        """Returns a copy of the cube translated with `translation`"""

        acopy = self.__class__.__new__(self.__class__)
        acopy.__dict__ = self.__dict__.copy()

        d = acopy.__dict__

        for attr in self.localizable_attributes:
            d[attr] = context.get(attr, getattr(self, attr))

        for attr in self.localizable_lists:
            list_copy = []

            if hasattr(acopy, attr):
                for obj in getattr(acopy, attr):
                    obj_context = context.object_localization(attr, obj.name)
                    list_copy.append(obj.localized(obj_context))
                    setattr(acopy, attr, list_copy)

        return acopy


def object_dict(objects, by_ref=False, error_message=None, error_dict=None):
    """Make an ordered dictionary from model objects `objects` where keys are
    object names. If `for_ref` is `True` then object's `ref` (reference) is
    used instead of object name. Keys are supposed to be unique in the list,
    otherwise an exception is raised."""

    if by_ref:
        items = ((obj.ref, obj) for obj in objects)
    else:
        items = ((obj.name, obj) for obj in objects)

    ordered = OrderedDict()

    for key, value in items:
        if key in ordered:
            error_message = error_message or "Duplicate key {key}"
            error_dict = error_dict or {}
            raise ModelError(error_message.format(key=key, **error_dict))
        ordered[key] = value

    return ordered


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

