# -*- coding=utf -*-
"""Logical model model providers."""
import json
import os
import re
import urllib2
import urlparse
import copy

from .common import IgnoringDictionary, get_logger, to_label
from .errors import *
from .extensions import get_namespace, initialize_namespace
from .model import *

__all__ = [
    "read_model_metadata",
    "read_model_metadata_bundle",
    "create_model_provider",
    "ModelProvider",

    "create_dimension",
    "create_level",

    # FIXME: Depreciated
    "load_model",
    "model_from_path",
    "create_model",
    "merge_models",
]

def create_model_provider(name, metadata):
    """Gets a new instance of a model provider with name `name`."""

    ns = get_namespace("model_providers")
    if not ns:
    # FIXME: depreciated. affected: formatter.py
        ns = initialize_namespace("model_providers", root_class=ModelProvider,
                                  suffix="_model_provider")

    try:
        factory = ns[name]
    except KeyError:
        raise CubesError("Unable to find model provider of type '%s'" % name)

    return factory(metadata)

def _json_from_url(url):
    """Opens `resource` either as a file with `open()`or as URL with
    `urllib2.urlopen()`. Returns opened handle. """

    parts = urlparse.urlparse(url)
    if parts.scheme in ('', 'file'):
        handle = open(parts.path)
    else:
        handle = urllib2.urlopen(url)

    try:
        desc = json.load(handle)
    except ValueError as e:
        raise SyntaxError("Syntax error in %s: %s" % (url, e.args))
    finally:
        handle.close()

    return desc


def read_model_metadata(source):
    """Reads a model description from `source` which can be a filename, URL,
    file-like object or a path to a directory. Returns a model description
    dictionary."""

    if isinstance(source, basestring):
        parts = urlparse.urlparse(source)
        if parts.scheme in ('', 'file') and os.path.isdir(parts.path):
            source = parts.path
            return read_model_metadata_bundle(source)
        else:
            return _json_from_url(source)
    else:
        return json.load(source)


def read_model_metadata_bundle(path):
    """Load logical model a directory specified by `path`.  Returns a model
    description dictionary."""

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


def load_model(resource, translations=None):
    raise Exception("load_model() was replaced by Workspace.add_model(), "
                    "please refer to the documentation for more information")


class ModelProvider(object):
    """Abstract class. Currently empty and used only to find other model
    providers."""

    requires_store = False

    def __init__(self, metadata=None):
        """Initializes a model provider and sets `metadata` – a model metadata
        dictionary.

        Instance variable `store` might be populated after the
        initialization. If the model provider requires an open store, it
        should advertise it through `True` value returned by provider's
        `requires_store()` method.  Otherwise no store is opened for the model
        provider. `store_name` is also set.

        Subclasses should call this method when they are implementing custom
        `__init__()`.

        """
        self.metadata = metadata
        self.store = None
        self.store_name = None

        # TODO: check for duplicates
        self.dimensions_metadata = {}
        for dim in metadata.get("dimensions", []):
            self.dimensions_metadata[dim["name"]] = dim

        self.cubes_metadata = {}
        for cube in metadata.get("cubes", []):
            self.cubes_metadata[cube["name"]] = cube

        self.options = metadata.get("options", {})

    def init_store(self, store, store_name):
        """Sets provider's store and store name. Override this method if you
        would like to perform post-initialization from the store."""
        self.store = store
        self.store_name = store_name

    def cube_options(self, cube_name):
        """Returns an options dictionary for cube `name`. The options
        dictoinary is merged model `options` metadata with cube's `options`
        metadata if exists. Cube overrides model's global (default)
        options."""

        options = dict(self.options)
        if cube_name in self.cubes_metadata:
            cube = self.cubes_metadata[cube_name]
            options.update(cube.get("options", {}))

        return options

    def cube_metadata(self, name):
        """Returns a cube metadata by combining model's global metadata and
        cube's metadata. Merged metadata dictionaries: `browser_options`,
        `mappings`, `joins`.
        """

        if name in self.cubes_metadata:
            metadata = dict(self.cubes_metadata[name])
        else:
            raise ModelError("Unknown cube --- %s" % name)
        return metadata

        # merge datastore from model if datastore not present
        if not metadata.get("datastore"):
            metadata['datastore'] = self.metadata.get("datastore")

        # merge browser_options
        browser_options = self.metadata.get('browser_options', {})
        if metadata.get('browser_options'):
            browser_options.update(metadata.get('browser_options'))
        metadata['browser_options'] = browser_options

        # Merge model and cube mappings
        #
        model_mappings = self.metadata.get("mappings")
        cube_mappings = metadata.pop("mappings", None)

        if model_mappings:
            mappings = copy.deepcopy(model_mappings)
            mappings.update(cube_mappings)
        else:
            mappings = cube_mappings

        metadata["mappings"] = mappings

        # Merge model and cube joins
        #
        model_joins = self.metadata.get("joins")
        cube_joins = metadata.pop("joins", None)

        # model joins, if present, should be merged with cube's overrides.
        # joins are matched by the "name" key.
        if cube_joins and model_joins:
            model_join_map = {}
            for join in model_joins:
                try:
                    name = join['name']
                except KeyError:
                    raise ModelError("Missing required 'name' key in "
                                     "model-level joins.")

                if name in model_join_map:
                    raise ModelError("Duplicate model-level join 'name': %s" %
                                     name)

                model_join_map[name] = copy.deepcopy(join)

            # Merge cube's joins with model joins by their names.
            merged_joins = []

            for join in cube_joins:
                model_join = model_join_map.get(join.get('name'), {})
                model_join.update(join)
                merged_joins.append(model_join)

        metadata["joins"] = merged_joins

    def list_cubes(self):
        """Get a list of metadata for cubes in the workspace. Result is a list
        of dictionaries with keys: `name`, `label`, `category`, `info`.

        The list is fetched from the model providers on the call of this
        method.
        """
        raise NotImplementedError("Subclasses should implement list_cubes()")
        return []

    def cube(self, name):
        """Returns a cube with `name` provided by the receiver. If receiver
        does not have the cube `ModelError` exception is raised.

        Returned cube has no dimensions assigned. You should assign the
        dimensions according to the cubes `linked_dimensions` list of
        dimension names."""
        raise NotImplementedError("Subclasses should implement cube() method")

    def dimension(self, name, dimensions=[]):
        """Returns a dimension with `name` provided by the receiver.
        `dimensions` is a dictionary of dimension objects where the receiver
        can look for templates. If the dimension requires a template and the
        template is missing, the subclasses should raise
        `TemplateRequired(template)` error with a template name as an
        argument.

        If the receiver does not provide the dimension `NoSuchDimension`
        exception is raised."""
        raise NotImplementedError("Subclasses are required to implement this")


class DefaultModelProvider(ModelProvider):

    dynamic_cubes = False
    dynamic_dimensions = False

    def list_cubes(self):
        cubes = []

        for cube in self.metadata.get("cubes", []):
            info = {
                    "name": cube["name"],
                    "label": cube.get("label", cube["name"]),
                    "category": (cube.get("category") or cube.get("info", {}).get("category")),
                    "info": cube.get("info", {})
                }
            cubes.append(info)

        return cubes

    def cube(self, name):
        """
        Creates a cube `name` in context of `workspace` from provider's
        metadata. The created cube has no dimensions attached. You sohuld link
        the dimensions afterwards according to the `linked_dimensions`
        property of the cube.
        """

        metadata = self.cube_metadata(name)
        return create_cube(metadata)

    def dimension(self, name, dimensions=None):
        """Create a dimension `name` from provider's metadata within
        `context` (usualy a `Workspace` object)."""

        # Old documentation
        """Creates a `Dimension` instance from `obj` which can be a `Dimension`
        instance or a string or a dictionary. If it is a string, then it
        represents dimension name, the only level name and the only attribute.

        Keys of a dictionary representation:

        * `name`: dimension name
        * `levels`: list of dimension levels (see: :class:`cubes.Level`)
        * `hierarchies` or `hierarchy`: list of dimension hierarchies or
           list of level names of a single hierarchy. Only one of the two
           should be specified, otherwise an exception is raised.
        * `default_hierarchy_name`: name of a hierarchy that will be used when
          no hierarchy is explicitly specified
        * `label`: dimension name that will be displayed (human readable)
        * `description`: human readable dimension description
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information (icon, color, ...)
        * `template` – name of a dimension to be used as template. The dimension
          is taken from `dimensions` argument which should be a dictionary
          of already created dimensions.

        **Defaults**

        * If no levels are specified during initialization, then dimension
          name is considered flat, with single attribute.
        * If no hierarchy is specified and levels are specified, then default
          hierarchy will be created from order of levels
        * If no levels are specified, then one level is created, with name
          `default` and dimension will be considered flat

        String representation of a dimension ``str(dimension)`` is equal to
        dimension name.

        Class is not meant to be mutable.

        Raises `ModelInconsistencyError` when both `hierarchy` and
        `hierarchies` is specified.

        """
        try:
            metadata = dict(self.dimensions_metadata[name])
        except KeyError:
            raise NoSuchDimensionError(name)

        return create_dimension(metadata, dimensions, name)


def fix_dimension_metadata(metadata):
    """Returns a dimension description as a dictionary. If provided as string,
    then it is going to be used as a name and as a single level."""

    if isinstance(metadata, basestring):
        return {"name":metadata, "levels": [metadata]}
    else:
        return metadata


def create_dimension(metadata, dimensions=None, name=None):
    """Create a dimension from a `metadata` dictionary."""

    metadata = fix_dimension_metadata(metadata)
    dimensions = dimensions or {}

    if "template" in metadata:
        template_name = metadata["template"]
        try:
            template = dimensions[template_name]
        except KeyError:
            raise TemplateRequired(template_name)

        levels = copy.deepcopy(template.levels)

        # Create copy of template's hierarchies, but reference newly
        # created copies of level objects
        hierarchies = []
        level_dict = dict((level.name, level) for level in levels)

        for hier in template.hierarchies.values():
            hier_levels = [level_dict[level.name] for level in hier.levels]
            hier_copy = Hierarchy(hier.name,
                                  hier_levels,
                                  label=hier.label,
                                  info=copy.deepcopy(hier.info))
            hierarchies.append(hier_copy)

        default_hierarchy_name = template.default_hierarchy_name
        label = template.label
        description = template.description
        info = template.info
    else:
        levels = None
        hierarchies = None
        default_hierarchy_name = None
        label = None
        description = None
        info = {}

    name = metadata.get("name") or name
    if not name:
        raise ModelError("Dimension has no name, neither explicit name provided")

    label = metadata.get("label") or label
    description = metadata.get("description") or description
    info = metadata.get("info") or info

    # Levels
    # ------

    levels_metadata = metadata.get("levels")

    if levels_metadata:
        levels = []

        for md in levels_metadata:
            level = create_level(md)
            levels.append(level)

    if not levels:
        # Create a single level with same properties as the dimension.
        attributes = ["attributes", "key", "order_attribute", "order",
                      "label_attribute"]
        level_md = {}
        for attr in attributes:
            if attr in metadata:
                level_md[attr] = metadata[attr]

        # Default: if no attributes, then there is single flat attribute
        # whith same name as the dimension
        level_md["name"] = name
        level_md["label"] = label

        levels = [create_level(level_md)]

    # Hierarchies
    # -----------

    if "hierarchy" in metadata and "hierarchies" in metadata:
        raise ModelInconsistencyError("Both 'hierarchy' and 'hierarchies'"
                                      " specified. Use only one")

    hierarchy = metadata.get("hierarchy")

    if hierarchy:
        # We consider it to be a list of level names
        if not isinstance(hierarchy, Hierarchy):
            hierarchy = Hierarchy("default", levels=hierarchy)

        hierarchies = [hierarchy]

    elif "hierarchies" in metadata:
        hierarchies = [Hierarchy(**md) for md in metadata["hierarchies"]]

    default_hierarchy_name = metadata.get("default_hierarchy_name",
                                          default_hierarchy_name)

    name = name or metadata["name"]

    return Dimension(name=name,
                     levels=levels,
                     hierarchies=hierarchies,
                     default_hierarchy_name=default_hierarchy_name,
                     label=label,
                     description=description,
                     info=info
                     )


def fix_level_metadata(metadata):
    """Returns a level description as a dictionary. If provided as string,
    then it is going to be used as level name and as its only attribute. If a
    dictionary is provided and has no attributes, then level will contain only
    attribute with the same name as the level name."""
    if isinstance(metadata, basestring):
        return {"name":metadata, "attributes": [metadata]}
    else:
        metadata = dict(metadata)
        if "attributes" not in metadata:
            try:
                metadata["attributes"] = [metadata["name"]]
            except KeyError:
                raise ModelError("Level has no name.")

        return metadata


def create_level(metadata, name=None, dimension=None):
    """Create a level object from metadata. `name` can override level name in
    the metadata."""

    metadata = dict(fix_level_metadata(metadata))

    try:
        name = name or metadata.pop("name")
    except KeyError:
        raise ModelError("No name specified in level metadata")

    attributes = attribute_list(metadata.pop("attributes"), dimension=dimension)

    return Level(name=name,
                 attributes=attributes,
                 dimension=dimension,
                 **metadata)


# TODO: is this still necessary?
def merge_models(models):
    """Merge multiple models into one."""

    dimensions = {}
    all_cubes = {}
    name = None
    label = None
    description = None
    info = {}
    locale = None

    for model in models:
        if name is None and model.name:
            name = model.name
        if label is None and model.label:
            label = model.label
        if description is None and model.description:
            description = model.description
        if info is None and model.info:
            info = copy.deepcopy(model.info)
        if locale is None and model.locale:
            locale = model.locale

        # dimensions, fail on conflicting names
        for dim in model.dimensions:
            if dimensions.has_key(dim.name):
                raise ModelError("Found duplicate dimension named '%s', cannot merge models" % dim.name)
            dimensions[dim.name] = dim

        # cubes, fail on conflicting names
        for cube in model.cubes.values():
            if all_cubes.has_key(cube.name):
                raise ModelError("Found duplicate cube named '%s', cannot merge models" % cube.name)
            model.remove_cube(cube)
            if cube.info is None:
                cube.info = {}
            cube.info.update(model.info if model.info else {})
            all_cubes[cube.name] = cube

    return Model(name=name,
                 label=label,
                 description=description,
                 info=info,
                 dimensions=dimensions.values(),
                 cubes=all_cubes.values())

def create_cube(metadata):
    """Create a cube object from `metadata` dictionary. The cube has no
    dimensions attached after creation. You should link the dimensions to the
    cube according to the `Cube.linked_dimensions` property using
    `Cube.add_dimension()`"""

    if "name" not in metadata:
        raise ModelError("Cube has no name")

    metadata = dict(metadata)
    dimensions = metadata.pop("dimensions", [])

    return Cube(linked_dimensions=dimensions,
                **metadata)

def create_model(source):
    raise NotImplementedError("create_model() is depreciated, use Workspace.add_model()")


def model_from_path(path):
    """Load logical model from a file or a directory specified by `path`.
    Returs instance of `Model`. """
    raise NotImplementedError("model_from_path is depreciated. use Workspace.add_model()")

# TODO: modernize
def simple_model(cube_name, dimensions, measures):
    """Create a simple model with only one cube with name `cube_name`and flat
    dimensions. `dimensions` is a list of dimension names as strings and
    `measures` is a list of measure names, also as strings. This is
    convenience method mostly for quick model creation for denormalized views
    or tables with data from a single CSV file.

    Example:

    .. code-block:: python

        model = simple_model("contracts",
                             dimensions=["year", "supplier", "subject"],
                             measures=["amount"])
        cube = model.cube("contracts")
        browser = workspace.create_browser(cube)
    """
    dim_instances = []
    for dim_name in dimensions:
        dim_instances.append(create_dimension(dim_name))

    cube = Cube(cube_name, dim_instances, measures)

    return Model(cubes=[cube])


