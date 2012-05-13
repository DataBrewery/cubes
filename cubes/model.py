"""Logical model."""

# FIXME: Model constructors contain lots of default initializations. This
# should be moved to some other place or made optional by a flag

import os
import re
import urllib2
import urlparse
import copy
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from cubes.common import IgnoringDictionary, get_logger

try:
    import json
except ImportError:
    import simplejson as json

__all__ = [
    "load_model",
    "model_from_path",
    "attribute_list",
    "coalesce_attribute",
    "Model",
    "Cube",
    "Dimension",
    "Hierarchy",
    "Level",
    "Attribute",
    "ModelError"
]

DIMENSION = 1
MEASURE = 2
DETAIL = 3

class ModelError(Exception):
    """Model related exception."""
    pass

def load_model(resource, translations = None):
    """Load logical model from object reference. `resource` can be an URL,
    local file path or file-like object.

    The ``path`` might be:

    * JSON file with a dictionary describing model
    * URL with a JSON dictionary
    """

    handle = None
    if isinstance(resource, basestring):
        parts = urlparse.urlparse(resource)
        should_close = True
        handle = open(resource) if parts.scheme in ('', 'file') else urllib2.urlopen(resource)
    else:
        handle = resource
        should_close = False

    try:
        model_desc = json.load(handle)
    finally:
        if should_close:
            handle.close()

    if type(model_desc) != dict:
        raise TypeError("Model description file should contain a dictionary")

    model = Model(**model_desc)

    if translations:
        for lang, path in translations.items():
            handle = urllib2.urlopen(path)
            trans = json.load(handle)
            handle.close()
            model._add_translation(lang, trans)

    return model

def model_from_path(path):
    """Load logical model from a file or a directory specified by `path`.
    Returs instance of `Model`. """

    # FIXME: refactor this/merge with load_model

    if not os.path.isdir(path):
        a_file = open(path)
        model_desc = json.load(a_file)
        a_file.close()
        return Model(**model_desc)

    info_path = os.path.join(path, 'model.json')

    if not os.path.exists(info_path):
        raise ModelError('main model info %s does not exist' % info_path)

    a_file = open(info_path)
    model_desc = json.load(a_file)
    a_file.close()

    if not "name" in model_desc:
        raise ModelError("model has no name")

    # Find model object files and load them

    dimensions_to_load = []
    cubes_to_load = []

    if not "dimensions" in model_desc:
        model_desc["dimensions"] = {}
    elif type(model_desc["dimensions"]) != dict:
        raise ModelError("dimensions object in model file be a dictionary")

    if not "cubes" in model_desc:
        model_desc["cubes"] = {}
    elif type(model_desc["cubes"]) != dict:
        raise ModelError("cubes object in model file should be a dictionary")

    for dirname, dirnames, filenames in os.walk(path):
        for filename in filenames:
            if os.path.splitext(filename)[1] != '.json':
                continue
            split = re.split('_', filename)
            prefix = split[0]

            obj_path = os.path.join(dirname, filename)
            if prefix == 'dim' or prefix == 'dimension':
                desc = _model_desc_from_json_file(obj_path)
                if "name" not in desc:
                    raise ModelError("Dimension file '%s' has no name key" % obj_path)
                model_desc["dimensions"][desc["name"]] = desc
            elif prefix == 'cube':
                desc = _model_desc_from_json_file(obj_path)
                if "name" not in desc:
                    raise ModelError("Cube file '%s' has no name key" % obj_path)
                model_desc["cubes"][desc["name"]] = desc

    return model_from_dict(model_desc)

def _model_desc_from_json_file(object_path):
    """Get a dictionary from reading model json file at `object_path`.
    Returs a dictionary from the file.
    """
    a_file = open(object_path)
    try:
        desc = json.load(a_file)
    except ValueError as e:
        raise SyntaxError("Syntaxt error in %s: %s" % (full_path, e.args))
    finally:
        a_file.close()

    return desc

class Model(object):
    def __init__(self, name=None, label=None, description=None,
                 cubes=None, dimensions=None, locale=None, **kwargs):
        """
        Logical Model represents analysts point of view on data.

        The `model` dictionary contains main model description. The structure
        is::

            {
            	"name": "public_procurements",
            	"label": "Procurements",
            	"description": "Procurement Contracts of an Organisation"
            	"cubes": {...}
            	"dimensions": {...}
            }

        Attributes:

        * `name` - model name
        * `label` - human readable name - can be used in an application
        * `description` - longer human-readable description of the model
        * `cubes` -  dictionary of cube descriptions (see below)
        * `dimensions` - dictionary of dimension descriptions (see below)
        * `locale` - locale code of the model

        When initializing the ``Model`` object, `cubes` and `dimensions` might
        be dictionaries with descriptions. See `Cube` and `Dimension` for more
        information.
        """

        self.name = name

        if label:
            self.label = label
        else:
            self.label = name

        self.description = description
        self.locale = locale

        self._dimensions = {}

        logger = get_logger()

        # TODO: allow dimension objects
        if dimensions:
            if isinstance(dimensions, dict):
                # logger.warn("model initialization: dimensions as dictionary "
                #             "is depreciated, use array instead")

                for dim_name, dim_desc in dimensions.items():
                    desc = dict([("name", dim_name)] + dim_desc.items())
                    dim = Dimension(**desc)
                    self.add_dimension(dim)
            else:
                for obj in dimensions:
                    if isinstance(obj, Dimension):
                        self.add_dimension(obj)
                    else:
                        self.add_dimension(Dimension(**obj))

        self.cubes = OrderedDict()

        if cubes:
            if isinstance(cubes, dict):
                # logger.warn("model initialization: cubes as dictionary is "
                #             "depreciated, use array instead")

                for cube_name, cube_desc in cubes.items():
                    desc = dict([("name", cube_name)] + cube_desc.items())
                    cube = Cube(model=self, **desc)
                    self.add_cube(cube)
            else:
                for obj in cubes:
                    if isinstance(obj, Cube):
                        if obj.model and obj.model != self:
                            raise Exception("adding cube from different model")
                        obj.model = self
                        self.add_cube(obj)
                    else:
                        self.add_cube(Cube(model=self,**obj))

        self.translations = {}

    def add_cube(self, cube):
        """Adds cube to the model and also assigns the model to the cube. If
        cube has a model assigned and it is not this model, then error is
        raised.

        Cube's dimensions are collected to the model. If cube has a dimension
        with same name as one of existing model's dimensions, but has
        different structure, an exception is raised. Dimensions in cube should
        be the same as in model.
        """
        if cube.model and cube.model != self:
            raise ModelError("Trying to assign a cube with different model (%s) to model %s" %
                (cube.model.name, self.name))

        # Collect dimensions from cube
        my_dimensions = set(self.dimensions)
        my_dimension_names = set([dim.name for dim in self.dimensions])

        for dimension in cube.dimensions:
            if dimension not in my_dimensions:
                if dimension.name not in my_dimension_names:
                    self.add_dimension(dimension)
                else:
                    raise ModelError("Dimension %s of cube %s has different specification as model's dimension"
                                            % (dimension.name, cube.name) )

        cube.model = self

        self.cubes[cube.name] = cube

    def remove_cube(self, cube):
        """Removes cube from the model"""
        cube.model = None
        del self.cubes[cube.name]

    def cube(self, cube):
        """Get a cube with name `name` or coalesce object to a cube."""
        if isinstance(cube, basestring):
            return self.cubes[cube]
        else:
            return self.cubes[cube.name]

    def add_dimension(self, dimension):
        """Add dimension to model. Replace dimension with same name"""
        self._dimensions[dimension.name] = dimension

    def remove_dimension(self, dimension):
        """Remove a dimension from receiver"""
        del self._dimensions[dimension.name]
        # FIXME: check whether the dimension is not used in cubes

    @property
    def dimensions(self):
        return self._dimensions.values()

    def dimension(self, obj):
        """Get dimension by name or by object"""
        if isinstance(obj, basestring):
            if obj in self._dimensions:
                return self._dimensions[obj]
            else:
                raise ModelError("Unknown dimension with name '%s' in model '%s'" % (obj, self.name))
        elif obj.name in self._dimensions:
            return obj
        else:
            raise ModelError("Unknown dimension '%s' in model '%s'" % (obj, self.name))

    def to_dict(self, **options):
        """Return dictionary representation of the model. All object
        references within the dictionary are name based

        * `expand_dimensions` - if set to True then fully expand dimension
          information in cubes
        * `full_attribute_names` - if set to True then attribute names will be
          written as ``dimension_name.attribute_name``
        """

        out = IgnoringDictionary()

        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("description", self.description)

        dims = {}
        for dim in self._dimensions.values():
            dims[dim.name] = dim.to_dict(**options)

        out.setnoempty("dimensions", dims)

        cubes = {}
        for cube in self.cubes.values():
            cubes[cube.name] = cube.to_dict(**options)

        out.setnoempty("cubes", cubes)

        return out

    def validate(self):
        """Validate the model, check for model consistency. Validation result
        is array of tuples in form: (validation_result, message) where
        validation_result can be 'warning' or 'error'.

        Returs: array of tuples
        """

        results = []

        ################################################################
        # 1. Chceck dimensions
        is_fatal = False
        for dim_name, dim in self._dimensions.items():
            if not issubclass(dim.__class__, Dimension):
                results.append(('error', "Dimension '%s' is not a subclass of Dimension class" % dim_name))
                is_fatal = True

        # We are not going to continue if there are no valid dimension objects, as more errors migh emerge
        if is_fatal:
            return results

        for dim in self.dimensions:
            results.extend(dim.validate())

        ################################################################
        # 2. Chceck cubes

        if not self.cubes:
            results.append( ('warning', 'No cubes defined') )
        else:
            for cube_name, cube in self.cubes.items():
                results.extend(cube.validate())

        return results

    def is_valid(self, strict = False):
        """Check whether model is valid. Model is considered valid if there
        are no validation errors. If you want to be sure that there are no
        warnings as well, set *strict* to ``True``. If `strict` is ``False``
        only errors are considered fatal, if ``True`` also warnings will make
        model invalid.

        Returns ``True`` when model is valid, otherwise returns ``False``.
        """
        results = self.validate()
        if not results:
            return True

        if strict:
            return False

        for result in results:
            if result[0] == 'error':
                return False

        return True

    def _add_translation(self, lang, translation):
        self.translations[lang] = translation

    def localize(self, translation):
        """Return localized version of model"""

        model = copy.deepcopy(self)

        if type(translation) == str or type(translation) == unicode:
            translation = self.translations[translation]

        if "locale" not in translation:
            raise ValueError("No locale specified in model translation")

        model.locale = translation["locale"]
        localize_common(model, translation)

        if "cubes" in translation:
            for name, cube_trans in translation["cubes"].items():
                cube = model.cube(name)
                cube.localize(cube_trans)

        if "dimensions" in translation:
            for name, dim_trans in translation["dimensions"].items():
                dim = model.dimension(name)
                dim.localize(dim_trans)

        return model

    def localizable_dictionary(self):
        """Get model locale dictionary - localizable parts of the model"""
        locale = {}
        locale.update(get_localizable_attributes(self))
        clocales = {}
        locale["cubes"] = clocales
        for cube in self.cubes.values():
            clocales[cube.name] = cube.localizable_dictionary()

        dlocales = {}
        locale["dimensions"] = dlocales
        for dim in self.dimensions:
            dlocales[dim.name] = dim.localizable_dictionary()

        return locale


class Cube(object):
    """
    OLAP Cube
    """

    def __init__(self, name=None, model=None, label=None, measures=None,
                 details=None, dimensions=None, mappings=None, joins=None,
                 fact=None, key=None, description=None, options=None, **kwargs):
        """Create a new OLAP Cube

        Attributes:

        * `name`: dimension name
        * `model`: model the cube belongs to
        * `label`: human readable cube label
        * `measures`: list of measure attributes
        * `details`: list of detail attributes
        * `dimensions`: list of dimensions or dimension names. They should
          be present in the `model`.
        * `description` - human readable description of the cube
        * `key`: fact key field (if not specified, then backend default key
          will be used, mostly ``id`` for SLQ or ``_id`` for document based
          databases)

        Attributes used by backends:

        * `mappings` - backend-specific logical to physical mapping
          dictionary
        * `joins` - backend-specific join specification (used in SQL
          backend)
        * `fact` - fact dataset (table) name (physical reference)
        * `options` - dictionary of other options used by the backend - refer
          to the backend documentation to see what options are used (for
          example SQL browser might look here for ``denormalized_view`` in
          case of denormalized browsing)
            
        In file based model representation, the cube descriptions are stored
        in json files with prefix ``cube_`` like ``cube_contracts``, or as a
        dictionary for key ``cubes`` in the model description dictionary.

        JSON example::

            {
                "name": "contracts",
                "measures": ["amount"],
                "dimensions": [ "date", "contractor", "type"]
                "details": ["contract_name"],
            }
        """
        self.name = name

        self.label = label
        self.description = description

        logger = get_logger()

        self.measures = attribute_list(measures)
        self.details = attribute_list(details)

        # TODO: put this in a separate dictionary - this is backend-specific
        self.mappings = mappings
        self.fact = fact
        self.joins = joins
        self.key = key
        self.options = options

        # This is stored to get dimensions, if dimensions are not defined in-place
        self.model = model

        self._dimensions = OrderedDict()

        if dimensions:
            for obj in dimensions:
                if isinstance(obj, basestring):
                    dimension = self.model.dimension(obj)
                    self.add_dimension(dimension)
                elif isinstance(obj, Dimension):
                    self.add_dimension(dimension)
                else:
                    logger.warn("creating dimensions during cube initialization"
                                " is depreciated: dimensions should be present in model")
                    desc = dict([("name", obj["name"])] + obj.items())
                    dimension = Dimension(**desc)
                    self.add_dimension(dimension)

    def add_dimension(self, dimension):
        """Add dimension to cube. Replace dimension with same name"""

        # FIXME: Do not allow to add dimension if one already exists
        if dimension.name in self._dimensions:
            raise ModelError("Dimension with name %s already exits in cube %s" % (dimension.name, self.name))

        self._dimensions[dimension.name] = dimension

    def remove_dimension(self, dimension):
        """Remove a dimension from receiver. `dimension` can be either
        dimension name or dimension object."""

        dim = self.dimension(dimension)
        del self._dimensions[dim.name]

    @property
    def dimensions(self):
        return self._dimensions.values()

    def dimension(self, obj):
        """Get dimension object. If `obj` is a string, then dimension with
        given name is returned, otherwise dimension object is returned if it
        belongs to the cube."""

        if isinstance(obj, basestring):
            if obj in self._dimensions:
                return self._dimensions[obj]
            else:
                raise ModelError("cube '%s' has no dimension '%s'" %
                                    (self.name, obj))
        elif isinstance(obj, Dimension):
             return obj
        else:
            raise ModelError("Invalid dimension or dimension reference '%s' for cube '%s'" %
                                    (obj, self.name))

    def measure(self, obj):
        """Get measure object. If `obj` is a string, then measure with given
        name is returned, otherwise measure object is returned if it belongs
        to the cube. Returned object is of `Attribute` type"""

        if isinstance(obj, basestring):
            lookup = [m for m in self.measures if m.name == obj]
            if lookup:
                if len(lookup) == 1:
                    return lookup[0]
                else:
                    raise ModelError("multiple measures with the same name '%s' found" % obj)
            else:
                raise ModelError("cube '%s' has no measure '%s'" %
                                    (self.name, obj))
        elif isinstance(obj, Attribute):
             return obj
        else:
            raise ModelError("Invalid measure or measure reference '%s' for cube '%s'" %
                                    (obj, self.name))

    def to_dict(self, expand_dimensions=False, with_mappings=True, **options):
        """Convert to a dictionary. If `expand_dimensions` is ``True``
        (default is ``False``) then fully expand dimension information If
        `with_mappings` is ``True`` (which is default) then `joins`,
        `mappings`, `fact` and `options` are included. Should be set to
        ``False`` when returning a dictionary that will be provided in an user
        interface or through server API.
        """

        out = IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)

        array = []
        for attr in self.measures:
            array.append(attr.to_dict())
        out.setnoempty("measures", array)

        array = []
        for attr in self.details:
            array.append(attr.to_dict())
        out.setnoempty("details", array)

        if expand_dimensions:
            dims = [dim.to_dict(**options) for dim in self.dimensions]
        else:
            dims = [dim.name for dim in self.dimensions]

        out.setnoempty("dimensions", dims)

        if with_mappings:
            out.setnoempty("mappings", self.mappings)
            out.setnoempty("fact", self.fact)
            out.setnoempty("joins", self.joins)
            out.setnoempty("options", self.options)

        out.setnoempty("key", self.key)

        return out

    def validate(self):
        """Validate cube. See Model.validate() for more information. """
        results = []

        # Check whether all attributes, measures and keys are Attribute objects
        # This is internal consistency chceck

        measures = set()

        for measure in self.measures:
            if not isinstance(measure, Attribute):
                results.append( ('error', "Measure '%s' in cube '%s' is not instance of Attribute" % (measure, self.name)) )
            if str(measure) in measures:
                results.append( ('error', "Duplicate measure '%s' in cube '%s'"\
                                            % (measure, self.name)) )
            else:
                measures.add(str(measure))

        details = set()
        for detail in self.details:
            if not isinstance(detail, Attribute):
                results.append( ('error', "Detail '%s' in cube '%s' is not instance of Attribute" % (detail, self.name)) )
            if str(detail) in details:
                results.append( ('error', "Duplicate detail '%s' in cube '%s'"\
                                            % (detail, self.name)) )
            elif str(detail) in measures:
                results.append( ('error', "Duplicate detail '%s' in cube '%s'"
                                          " - specified also as measure" \
                                            % (detail, self.name)) )
            else:
                details.add(str(detail))

        # 2. check whether dimension attributes are unique

        return results

    def localize(self, locale):
        localize_common(self,locale)

        attr_locales = locale.get("measures")
        if attr_locales:
            for attrib in self.measures:
                if attrib.name in attr_locales:
                    localize_common(attrib, attr_locales[attrib.name])

        attr_locales = locale.get("details")
        if attr_locales:
            for attrib in self.details:
                if attrib.name in attr_locales:
                    localize_common(attrib, attr_locales[attrib.name])

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        mdict = {}
        locale["measures"] = mdict

        for measure in self.measures:
            mdict[measure.name] = measure.localizable_dictionary()

        mdict = {}
        locale["details"] = mdict

        for measure in self.details:
            mdict[measure.name] = measure.localizable_dictionary()

        return locale

class Dimension(object):
    """
    Cube dimension.

    """

    def __init__(self, name=None, label=None, levels=None,
                 attributes=None, hierarchy=None, description=None, **desc):
        """Create a new dimension

        Attributes:

    	* `name`: dimension name
    	* `label`: dimension name that will be displayed (human readable)
    	* `levels`: list of dimension levels (see: :class:`cubes.Level`)
    	* `hierarchies`: list of dimension hierarchies
    	* `default_hierarchy_name`: name of a hierarchy that will be used when
          no hierarchy is explicitly specified

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
        """
        self.name = name

        self.label = label
        self.description = description

        logger = get_logger()

        # FIXME: make this an OrderedDict
        # If there are not levels, create one default level with one default attribute
        self._levels = OrderedDict()

        if not levels:
            if not attributes:
                attributes = [self.name]
            level = Level(name="default", dimension=self, attributes=attributes)
            self._levels["default"] = level
        else:
            if isinstance(levels, dict):
                # logger.warn("dimension initialization: levels as dictionary "
                #             "is depreciated, use list instead")

                for level_name, level_info in levels.items():
                    # FIXME: this is a hack for soon-to-be obsolete level specification
                    info = dict([("name", level_name)] + level_info.items())
                    level = Level(dimension=self, **info)
                    self._levels[level_name] = level

            else: # a tuple/list expected

                for level_info in levels:
                    if isinstance(level_info, basestring):
                        level = Level(dimension=self, name=level_info, attributes=[level_info])
                    else:
                        level = Level(dimension=self, **level_info)

                    self._levels[level.name] = level

        hierarchies = desc.get("hierarchies")

        if hierarchy and hierarchies:
            raise ModelError("Both 'hierarchy' and 'hierarchies' specified. "
                             "Use only one")

        if hierarchy:
            if type(hierarchy) == list or type(hierarchy) == tuple:
                hier = { "levels": hierarchy, "name": "default" }
            else:
                hier = hierarchy
            hierarchies =  { "default": hier }

        # Initialize hierarches from description dictionary

        # FIXME: Use ordered dictionary
        self.hierarchies = {}

        if hierarchies:
            for hier_name, hier_info in hierarchies.items():
                hdesc = {"name":hier_name}
                hdesc.update(hier_info)

                hier = Hierarchy(dimension=self, **hdesc)
                self.hierarchies[hier_name] = hier
        else: # if there is no hierarchy specified
            hier = Hierarchy(dimension=self,name="default",levels=self.levels)
            self.hierarchies["default"] = hier

        self._flat_hierarchy = None

        self.default_hierarchy_name = desc.get("default_hierarchy", None)
        self.key_field = desc.get("key_field")

    def __eq__(self, other):
        if other is None or type(other) != type(self):
            return False
        if self.name != other.name or self.label != other.label \
            or self.description != other.description:
            return False
        elif self.default_hierarchy != other.default_hierarchy:
            return False

        if self._levels != other._levels:
            return False

        if other.hierarchies != self.hierarchies:
            return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def has_details(self):
        """Returns ``True`` when each level has only one attribute, usually
        key."""

        return any([level.has_details for level in self._levels.values()])

    @property
    def levels(self):
        """Get list of all dimension levels. Order is not guaranteed, use a
        hierarchy to have known order."""
        return self._levels.values()

    @property
    def level_names(self):
        """Get list of level names. Order is not guaranteed, use a hierarchy
        to have known order."""
        return self._levels.keys()

    def level(self, obj):
        """Get level by name or as Level object. This method is used for
        coalescing value"""
        if isinstance(obj, basestring):
            if obj not in self._levels:
                raise KeyError("No level %s in dimension %s" % (obj, self.name))
            return self._levels[obj]
        elif isinstance(obj, Level):
            return obj
        else:
            raise ValueError("Unknown level object %s (should be a string or Level)" % obj)

    def hierarchy(self, obj=None):
        """Get hierarchy object either by name or as `Hierarchy`. If `obj` is
        ``None`` then default hierarchy is returned."""

        # TODO: this should replace default_hierarchy constructed property
        #       see Issue #46

        if obj is None:
            return self.default_hierarchy
        if isinstance(obj, basestring):
            if obj not in self.hierarchies:
                raise KeyError("No hierarchy %s in dimension %s" % (obj, self.name))
            return self.hierarchies[obj]
        elif isinstance(obj, Hierarchy):
            return obj
        else:
            raise ValueError("Unknown hierarchy object %s (should be a string or Hierarchy instance)" % obj)

    @property
    def default_hierarchy(self):
        """Get default hierarchy specified by ``default_hierarchy_name``, if
        the variable is not set then get a hierarchy with name *default*
        
        .. warning::
        
            Depreciated. Use `Dimension.hierarchy()` instead.
            
        """

        # TODO: depreciate this in favor of hierarchy() (without arguments or
        #       with None). See Issue #46

        if self.default_hierarchy_name:
            hierarchy_name = self.default_hierarchy_name
        else:
            hierarchy_name = "default"

        hierarchy = self.hierarchies.get(hierarchy_name)

        if not hierarchy:
            if len(self.hierarchies) == 1:
                hierarchy = self.hierarchies.values()[0]
            else:
                if not self.hierarchies:
                    if len(self.levels) == 1:
                        if not self._flat_hierarchy:
                            self._flat_hierarchy = Hierarchy(name=level.name,
                                                             dimension=self,
                                                             levels=[levels[0]])

                        return self._flat_hierarchy
                    elif len(self.levels) > 1:
                        raise KeyError("There are no hierarchies in dimenson %s "
                                       "and there are more than one level" % self.name)
                    else:
                        raise KeyError("There are no hierarchies in dimenson %s "
                                       "and there are no levels to make hierarchy from" % self.name)
                else:
                    raise KeyError("No default hierarchy specified in dimension '%s' " \
                                   "and there is more (%d) than one hierarchy defined" \
                                   % (self.name, len(self.hierarchies)))

        return hierarchy

    @property
    def is_flat(self):
        """Return true if dimension has only one level"""
        return len(self.levels) == 1

    def attribute_reference(self, attribute, locale=None):
        """Return an Attribute object if it is a string, otherwise just return
        the object."""
        if isinstance(attribute, basestring):
            attr = Attribute(attribute,locale=locale)
            return attr.full_name(dimension=self)
        else:
            return attribute.full_name(dimension=self)

    def key_attributes(self):
        """Return all dimension key attributes, regardless of hierarchy. Order
        is not guaranteed, use a hierarchy to have known order."""

        return [level.key for level in self._levels.values()]

    def all_attributes(self, hierarchy = None):
        """Return all dimension attributes regardless of hierarchy. Order is
        not guaranteed, use a hierarchy to have known order. Order of
        attributes within level is preserved."""

        attributes = []
        for level in self.levels:
            attributes.extend(level.attributes)

        return attributes

    def to_dict(self, **options):
        """Return dictionary representation of the dimension"""

        out = IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("default_hierarchy_name", self.default_hierarchy_name)

        levels_dict = {}
        for level in self.levels:
            levels_dict[level.name] = level.to_dict(**options)
        out["levels"] = levels_dict

        hier_dict = {}
        for hier in self.hierarchies.values():
            hier_dict[hier.name] = hier.to_dict(**options)
        out["hierarchies"] = hier_dict

        # Use only for reading, during initialization these keys are ignored, as they are derived
        # They are provided here for convenience.
        out["is_flat"] = self.is_flat
        out["has_details"] = self.has_details


        # * levels: list of dimension levels (see: :class:`brewery.cubes.Level`)
        # * hierarchies: list of dimension hierarchies

        return out

    def validate(self):
        """Validate dimension. See Model.validate() for more information. """
        results = []

        if not self.levels:
            results.append( ('error', "No levels in dimension '%s'" \
                                        % (self.name)) )
            return results

        if not self.hierarchies:
            msg = "No hierarchies in dimension '%s'" % (self.name)
            if self.is_flat:
                level = self.levels[0]
                results.append( ('default', msg + ", flat level '%s' will be used" % (level.name)) )
            elif len(self.levels) > 1:
                results.append( ('error', msg + ", more than one levels exist (%d)" % len(self.levels)) )
            else:
                results.append( ('error', msg) )
        else: # if self.hierarchies
            if not self.default_hierarchy_name:
                if len(self.hierarchies) > 1 and not "default" in self.hierarchies:
                    results.append( ('error', "No defaut hierarchy specified, there is "\
                                              "more than one hierarchy in dimension '%s'" % self.name) )
                # else:
                #     def_name = self.hierarchy().name
                #     results.append( ('default', "No default hierarchy name specified in dimension '%s', using "
                #                                 "'%s'"% (self.name, def_name)) )

        if self.default_hierarchy_name and not self.hierarchies.get(self.default_hierarchy_name):
            results.append( ('error', "Default hierarchy '%s' does not exist in dimension '%s'" % 
                            (self.default_hierarchy_name, self.name)) )

        
        attributes = set()
        first_occurence = {}
        
        for level_name, level in self._levels.items():
            if not level.attributes:
                results.append( ('error', "Level '%s' in dimension '%s' has no attributes" % (level.name, self.name)) )
                continue

            if not level.key:
                attr = level.attributes[0]
                results.append( ('default', "Level '%s' in dimension '%s' has no key attribute specified, "\
                                            "first attribute will be used: '%s'" 
                                            % (level.name, self.name, attr)) )

            if level.attributes and level.key:
                if str(level.key) not in [str(a) for a in level.attributes]:
                    results.append( ('error', 
                                     "Key '%s' in level '%s' in dimension "
                                     "'%s' is not in level's attribute list" \
                                     % (level.key, level.name, self.name)) )

            for attribute in level.attributes:
                attr_name = attribute.full_name()
                if attr_name in attributes:
                    first = first_occurence[attr_name]
                    results.append( ('error', 
                                     "Duplicate attribute '%s' in dimension "
                                     "'%s' level '%s' (also defined in level "
                                     "'%s')" % (attribute, self.name, 
                                              level_name, first)) )
                else:
                    attributes.add(attr_name)
                    first_occurence[attr_name] = level_name
                
                if not isinstance(attribute, Attribute):
                    results.append( ('error', 
                                     "Attribute '%s' in dimension '%s' is "
                                     "not instance of Attribute" \
                                     % (attribute, self.name)) )
                                     
                if attribute.dimension != self:
                    results.append( ('error',
                                     "Dimension (%s) of attribute '%s' does "
                                     "not match with owning dimension %s" \
                                     % (attribute.dimension, attribute, 
                                     self.name)) )

        return results

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<dimension: {name: '%s', levels: %s}>" % \
                            (self.name, self._levels.keys())

    def localize(self, locale):
        localize_common(self, locale)

        level_locales = locale.get("levels")
        if level_locales:
            for level in self.levels:
                level_locale = level_locales.get(level.name)
                level.localize(level_locale)

        hier_locales = locale.get("hierarcies")
        if hier_locales:
            for hier in self.hierarchies:
                hier_locale = hier_locales.get(hier.name)
                hier.localize(hier_locale)

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        ldict = {}
        locale["levels"] = ldict

        for level in self.levels:
            ldict[level.name] = level.localizable_dictionary()

        hdict = {}
        locale["hierarchies"] = hdict

        for hier in self.hierarchies.values():
            hdict[hier.name] = hier.localizable_dictionary()

        return locale

class Hierarchy(object):
    """Dimension hierarchy - specifies order of dimension levels.

    Attributes:

    * `name`: hierarchy name
    * `label`: human readable name
    * `levels`: ordered list of levels from dimension

    Some collection operations might be used, such as ``level in hierarchy``
    or ``hierarchy[index]``. String value ``str(hierarchy)`` gives the
    hierarchy name.

    """
    def __init__(self, name=None, levels=None, label=None, dimension=None):
        self.name = name
        self.label = label
        self.dimension = dimension
        self._levels = OrderedDict()
        self._set_levels(levels)

    @property
    def levels(self):
        return self._levels.values()

    def _set_levels(self, levels):
        self._levels = OrderedDict()
        levels = levels or []

        for level in levels:
            if isinstance(level, basestring):
                if not self.dimension:
                    raise ModelError("Unable to set hierarchy level '%s' by name, no dimension specified"
                                        % level)
                level = self.dimension.level(level)
            self._levels[level.name] = level

    def __eq__(self, other):
        if not other or type(other) != type(self):
            return False
        elif self.name != other.name or self.label != other.label:
            return False
        elif self.levels != other.levels:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.name

    def __len__(self):
        return len(self.levels)

    def __getitem__(self, item):
        return self.levels[item]
        
    def __contains__(self, item):
        return item in self.levels

    def levels_for_path(self, path, drilldown = False):
        """Returns levels for given path. If path is longer than hierarchy
        levels, exception is raised"""

        if not path:
            if drilldown:
                return self.levels[0:1]
            else:
                return []

        extend = 1 if drilldown else 0
        
        if len(path) + extend > len(self.levels):
            raise AttributeError("Path %s is longer than hierarchy levels %s" % (path, self.level_names))

        return self.levels[0:len(path)+extend]

    def next_level(self, level):
        """Returns next level in hierarchy after `level`. If `level` is last
        level, returns ``None``. If `level` is ``None``, then the first level
        is returned."""

        if not level:
            return self.levels[0]
            
        if isinstance(level, basestring):
            level_name = level
        else:
            level_name = level.name

        index = self._levels.keys().index(level_name)
        if index + 1 >= len(self._levels):
            return None
        else:
            return self.levels[index + 1]

    def previous_level(self, level):
        """Returns previous level in hierarchy after `level`. If `level` is
        first level or ``None``, returns ``None``"""
        
        if level is None:
            return None
        
        if isinstance(level, basestring):
            level_name = level
        else:
            level_name = level.name

        index = self._levels.keys().index(level_name)
        if index == 0:
            return None
        else:
            return self.levels[index - 1]

    def level_index(self, level):
        """Get order index of level. Can be used for ordering and comparing
        levels within hierarchy."""
        return self._levels.keys().index(str(level))

    def rollup(self, path, level = None):
        """Rolls-up the path to the `level`. If `level` is None then path is
        rolled-up only one level. If `level` is deeper than last level of
        `path` the exception is raised. If `level` is the same as `path`
        level, nothing happens."""
        
        if level:
            level = self.dimension.level(level)
        
            last = self._levels.keys().index(level.name) + 1
            if last > len(path):
                raise ValueError("Can not roll-up: level '%s' in dimension '%s' is deeper than "
                                 "deepest element of path %s", level.name, self.dimension.name, path)
        else:
            if len(path) > 0:
                last = len(path) - 1
            else:
                last = None
                
        if last is None:
            return []
        else:
            return path[0:last]

    def path_is_base(self, path):
        """Returns True if path is base path for the hierarchy. Base path is a
        path where there are no more levels to be added - no drill down
        possible."""
        
        return path != None and len(path) == len(self._levels)

    def key_attributes(self):
        """Return all dimension key attributes as a single list."""

        return [level.key for level in self.levels]

    def all_attributes(self):
        """Return all dimension attributes as a single list."""

        attributes = []
        for level in self.levels:
            attributes.extend(level.attributes)

        return attributes

    def to_dict(self, **options):
        """Convert to dictionary. Keys:
        
        * `name`: hierarchy name
        * `label`: human readable label (localizable)
        * `levels`: level names
        
        """

        out = IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("levels", self._levels.keys())

        return out
        
    def localize(self, locale):
        localize_common(self,locale)

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        return locale

class Level(object):
    """Object representing a hierarchy level. Holds all level attributes.
    
    This object is immutable, except localization. You set up all attributes
    in the initialisation process.
    
    Attributes:

    * `name`: level name
    * `label`: human readable label 
    * `key`: key field of the level (customer number for customer level,
      region code for region level, year-month for month level). key will be
      used as a grouping field for aggregations. Key should be unique within
      level.
    * `label_attribute`: name of attribute containing label to be displayed
      (customer_name for customer level, region_name for region level,
      month_name for month level)
    * `attributes`: list of other additional attributes that are related to
      the level. The attributes are not being used for aggregations, they
      provide additional useful information
    """

    def __init__(self, name=None, key=None, attributes=None, null_value=None, 
                label=None, label_attribute=None, dimension=None):
        self.name = name
        self.label = label
        self.null_value = null_value

        self.attributes = attribute_list(attributes, dimension)
            
        self.dimension = dimension

        if key:
            self.key = coalesce_attribute(key, dimension)
        elif len(self.attributes) >= 1:
            self.key = coalesce_attribute(self.attributes[0].name, dimension)
        else:
            raise Exception("Level attribute list should not be empty")

        if label_attribute:
            self.label_attribute = coalesce_attribute(label_attribute, dimension)
        else:
            if len(self.attributes) > 1:
                self.label_attribute = coalesce_attribute(self.attributes[1], dimension)
            else:
                self.label_attribute = self.key

    def __eq__(self, other):
        if not other or type(other) != type(self):
            return False
        elif self.name != other.name or self.label != other.label or self.key != other.key:
            return False
        elif self.label_attribute != other.label_attribute:
            return False
        elif self.null_value != other.null_value:
            return False
        # elif self.dimension != other.dimension:
        #     return False

        if self.attributes != other.attributes:
            return False
            
        # for attr in other.attributes:
        #     if attr not in self.attributes:
        #         return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "<level: {name: '%s', key: %s, attributes: %s}>" % (self.name, self.key, self.attributes)
    def __repr__(self):
        return self.__str__()

    def to_dict(self, full_attribute_names=False, **options):
        """Convert to dictionary"""

        out = IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("missing_key_value", self.null_value)

        dimname = self.dimension.name

        key_name = str(self.key)
        if full_attribute_names:
            out.setnoempty("key", dimname + "." + key_name)
        else:
            out.setnoempty("key", key_name)

        array = []
        for attr in self.attributes:
            array.append(attr.to_dict(dimension=self.dimension, **options))
        out.setnoempty("attributes", array)
        out.setnoempty("label_attribute", str(self.label_attribute))

        return out

    @property
    def has_details(self):
        """Is ``True`` when level has more than one attribute, for all levels
        with only one attribute it is ``False``."""
        
        return len(self.attributes) > 1
            
    def localize(self, locale):
        localize_common(self,locale)
        
        attr_locales = locale.get("attributes")
        if attr_locales:
            for attrib in self.attributes:
                if attrib.name in attr_locales:
                    localize_common(attrib, attr_locales[attrib.name])

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        adict = {}
        locale["attributes"] = adict

        for attribute in self.attributes:
            adict[attribute.name] = attribute.localizable_dictionary()
            
        return locale


def attribute_list(attributes, dimension=None, attribute_class=None):
    """Create a list of attributes from a list of strings or dictionaries.
    see :func:`cubes.coalesce_attribute` for more information."""

    if not attributes:
        return []

    new_list = [coalesce_attribute(attr, dimension, attribute_class) for attr in attributes]

    return new_list

def coalesce_attribute(obj, dimension=None, attribute_class=None):
    """Makes sure that the `obj` is an ``Attribute`` instance. If `obj` is a
    string, then new instance is returned. If it is a dictionary, then the
    dictionary values are used for ``Attribute``instance initialization."""

    attribute_class = attribute_class or Attribute

    if isinstance(obj, basestring):
        return attribute_class(obj,dimension=dimension)
    elif isinstance(obj, dict):
        return attribute_class(dimension=dimension,**obj)
    else:
        return obj
    

class Attribute(object):
    
    ASC = 'asc'
    DESC = 'desc'
    
    def __init__(self, name, label=None, locales=None, order=None,
                description=None,dimension=None,aggregations=None, **kwargs):
        """Cube attribute - represents any fact field/column
        
        Attributes:

        * `name` - attribute name, used as identifier
        * `label` - attribute label displayed to a user
        * `locales` = list of locales that the attribute is localized to
        * `order` - default order of this attribute. If not specified, then
          order is unexpected. Possible values are: ``'asc'`` or ``'desc'``.
          It is recommended and safe to use ``Attribute.ASC`` and
          ``Attribute.DESC``
        * `aggregations` - list of default aggregations to be performed on
          this attribute if it is a measure. It is backend-specific, but most
          common might be: ``'sum'``, ``'min'``, ``'max'``, ...
          
        String representation of the `Attribute` returns its `name` (without
        dimension prefix).
        """
        super(Attribute, self).__init__()
        self.name = name
        self.label = label
        self.description = description
        self.dimension = dimension
        self.aggregations = aggregations
        
        if order:
            self.order = order.lower()
            if self.order.startswith("asc"):
                self.order = Attribute.ASC
            elif self.order.startswith("desc"):
                self.order = Attribute.DESC
            else:
                raise ValueError("Unknown ordering '%s' for attributes '%s'" % \
                                    (order, self.full_name) )
        else:
            self.order = None

        if locales == None:
            self.locales = []
        else:
            self.locales = locales
        
    def __str__(self):
        return self.name
        
    def __eq__(self, other):
        if type(other) != Attribute:
            return False

        return self.name == other.name and self.label == other.label \
                    and self.locales == other.locales
        
    def __ne__(self,other):
        return not self.__eq__(other)
        
    def to_dict(self, dimension = None, **options):
        d = {"name": self.name}
        if self.label is not None:
            d["label"] = self.label
        if self.locales:
            d["locales"] = self.locales
        if self.order is not None:
            d["order"] = self.order
        if self.description is not None:
            d["description"] = self.description
        if self.aggregations is not None:
            d["aggregations"] = self.aggregations
        if dimension:
            d["full_name"] = self.full_name(dimension)
        return d
        
    def ref(self, locale=None, simplify=False):
        """Return full attribute reference. Append `locale` if it is one of of
        attribute's locales, otherwise raise an error. If `simplify` is
        ``True``, then reference to an attribute of flat dimension without
        details will be just the dimension name.
        
        .. warning::
        
            This might change. Might be renamed.
            
        """
        if locale:
            if locale in self.locales:
                raise ValueError("Attribute '%s' has no localization %s" % self.name)
            else:
                locale_suffix = "." + locale
        else:
            locale_suffix = ""

        if self.dimension:
            if simplify and (self.dimension.is_flat and not self.dimension.has_details):
                reference = self.dimension.name
            else:
                reference = self.dimension.name + '.' + str(self.name)
        else:
            reference = str(self.name)

        return reference + locale_suffix

    def full_name(self, dimension=None, locale=None):
        """Return full name of an attribute as if it was part of `dimension`.
        Append `locale` if it is one of of attribute's locales, otherwise
        raise an error. """
        # Old behaviour: If no locale is specified and attribute is localized, then first locale from
        # list of locales is used.

        # FIXME: Deprecate dimension, use dimension on initialisation and each
        # attribute should have one assigned.

        if locale:
            if locale in self.locales:
                raise ValueError("Attribute '%s' has no localization %s" % self.name)
            else:
                locale_suffix = "." + locale
        else:
            locale_suffix = ""

        dimension = self.dimension or dimension

        return str(dimension) + "." + self.name + locale_suffix

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        return locale

def localize_common(obj, trans):
    """Localize common attributes: label and description"""
    if "label" in trans:
        obj.label = trans["label"]
    if "description" in trans:
        obj.description = trans["description"]


def localize_attributes(attribs, translations):
    """Localize list of attributes. `translations` should be a dictionary with
    keys as attribute names, values are dictionaries with localizable
    attribute metadata, such as ``label`` or ``description``."""
    for (name, atrans) in translations.items():
        attrib = attribs[name]
        localize_common(attrib, atrans)


def get_localizable_attributes(obj):
    """Returns a dictionary with localizable attributes of `obj`."""

    # FIXME: use some kind of class attribute to get list of localizable attributes

    locale = {}
    if hasattr(obj,"label"):
        locale["label"] = obj.label

    if hasattr(obj, "description"):
        locale["description"] = obj.description

    return locale
