"""Logical model."""

# FIXME: Model constructors contain lots of default initializations. This should be moved to some other
# place or made optional by a flag

import os
import re
import urllib2
import urlparse
import copy
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from cubes.util import IgnoringDictionary
import cubes.util as util

try:
    import json
except ImportError:
    import simplejson as json

DIMENSION = 1
MEASURE = 2
DETAIL = 3

class ModelError(Exception):
    """Model related exception."""
    pass
    
def load_model(resource, translations = None):
    """Load logical model from object reference. `resource` can be an URL, local file path or file-like
    object.
    
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
    """Load logical model from a directory specified by path

    Argrs:
        path: directory where model is located

    Returs:
        instance of Model
    """

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
    """Get a dictionary from reading model json file

    Args:
        pbject_path: path within model directory

    Returs:
        dict object
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
    """
    Logical Model represents analysts point of view on data.

    The `model` dictionary contains main model description. The structure is::

        {
        	"name": "public_procurements",
        	"label": "Public Procurements of Slovakia",
        	"description": "Contracts of public procurement winners in Slovakia"
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
    
    When initializing the ``Model`` object, `cubes` and `dimensions` might be dictionaries with
    descriptions. See `Cube` and `Dimension` for more information.
    """

    def __init__(self, name = None, label = None, description = None, 
                 cubes = None, dimensions = None, locale = None, **kwargs):

    	self.name = name

        if label:
    	    self.label = label
    	else:
    	    self.label = name

    	self.description = description
    	self.locale = locale

    	self._dimensions = {}

        # FIXME: pythonify: allow dimension objects
    	if dimensions:
            if isinstance(dimensions, dict):
                for dim_name, dim_desc in dimensions.items():
                    desc = dict([("name", dim_name)] + dim_desc.items())
                    dim = Dimension(**desc)
                    self.add_dimension(dim)
            else:
                for desc in dimensions:
                    self.add_dimension(Dimension(**desc))

        self.cubes = OrderedDict()

    	if cubes:
            if isinstance(cubes, dict):
                for cube_name, cube_desc in cubes.items():
                    desc = dict([("name", cube_name)] + cube_desc.items())
                    cube = Cube(model=self, **desc)
                    self.add_cube(cube)
            else:
                for desc in cubes:
                    self.add_cube(Cube(model=self,**desc))
    	        
        self.translations = {}
        
    def add_cube(self, cube):
        """Adds cube to the model and also assigns the model to the cube. If cube has a model assigned
        and it is not this model, then error is raised.
        
        Cube's dimensions are collected to the model. If cube has a dimension with same name as one of
        existing model's dimensions, but has different structure, an exception is raised. Dimensions
        in cube should be the same as in model.
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
        """Return dictionary representation of the model. All object references within the dictionary are
        name based

        Options:
        
            * `expand_dimensions` - if set to True then fully expand dimension information in cubes
            * `full_attribute_names` - if set to True then attribute names will be written as
              ``dimension_name.attribute_name``
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
        """Validate the model, check for model consistency. Validation result is array of tuples in form:
        (validation_result, message) where validation_result can be 'warning' or 'error'.
        
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
        """Check whether model is valid. Model is considered valid if there are no validation errors. If you want
        to be sure that there are no warnings as well, set *strict* to ``True``.
        
        Args:
            * strict: If ``False`` only errors are considered fatal, if ``True`` also warnings will make model invalid.
            
        Returns:
            boolean flag whether model is valid or not.
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
        util.localize_common(model, translation)
            
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
        locale.update(util.get_localizable_attributes(self))
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
    
    Attributes:
    
	* name: cube name
	* model: logical model cube belongs to
	* label: name that will be displayed (human readable)
	* measures: list of fact measures
	* details: list attributes that give more information about facts, but are not relevant
      from analysis or aggregation point of view in this context
	* dimensions: list of fact dimensions
	* mappings: map logical attributes to physical dataset fields (table columns)
	* joins: specification of physical table joins (order matters)
    * fact: dataset containing facts (fact table)
    * key: fact key field (if not specified, then backend default key will be used, mostly
      ``id`` for SLQ or ``_id`` for document based databases)

    Initialization defaults:
    
    * ``measures`` and details might be a list of attribute names as strings
    * ``dimensions`` might be either list of dimension names that are defined in ``model`` or might be
      dimension descriptions represented as a dictionary


    In file based model representation, the cube descriptions are stored in json files with prefix
    ``cube_`` like ``cube_contracts``, or as a dictionary for key ``cubes`` in the model description
    dictionary.

    JSON example::

        {
            "name": "contracts",

            "measures": ["amount"],
            "dimensions": [ "date", "contractor", "type"]
            "details": ["contract_name"],
        }

    """

    def __init__(self, name = None, model = None, label= None, measures = None, 
                 details = None, dimensions = None, mappings = None, joins = None,
                 fact = None, key = None, description = None, **kwargs):
        """Create a new cube

        Args:
            * name (str): dimension name
            * desc (dict): dict object containing keys label, description, dimensions, ...
        """
        self.name = name

        self.label = label
        self.description = description
        if measures == None:
            self.measures = attribute_list([])
        else:
            self.measures = attribute_list(measures)

        if details is None:
            self.details = attribute_list([])
        else:
            self.details = attribute_list(details)

        self.mappings = mappings
        self.fact = fact
        self.joins = joins
        self.key = key

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
        """Remove a dimension from receiver. `dimension` can be either dimension name or dimension object."""
        dim = self.dimension(dimension)
        del self._dimensions[dim.name]

    @property
    def dimensions(self):
        return self._dimensions.values()

    def dimension(self, obj):
        """Get dimension object. If `obj` is a string, then dimension with given name is returned, otherwise
        dimension object is returned if it belongs to the cube."""
        
        if isinstance(obj, basestring):
            if obj in self._dimensions:
                return self._dimensions[obj]
            else:
                raise ModelError("cube '%s' has no dimension '%s'" %
                                    (self.name, obj))
        elif issubclass(obj.__class__, Dimension):
             return obj
        else:
            raise ModelError("Invalid dimension or dimension reference '%s' for cube '%s'" %
                                    (obj, self.name))
            
    def to_dict(self, expand_dimensions = False, with_mappings = True, **options):
        """Convert to dictionary
        
        Options:
        
            * `expand_dimensions` - if set to True then fully expand dimension information
        
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

        out.setnoempty("key", self.key)

        return out

    def validate(self):
        """Validate cube. See Model.validate() for more information. """
        results = []

        # Check whether all attributes, measures and keys are Attribute objects
        # This is internal consistency chceck
        
        for measure in self.measures:
            if not isinstance(measure, Attribute):
                results.append( ('error', "Measure '%s' in cube '%s' is not instance of Attribute" % (measure, self.name)) )

        for detail in self.details:
            if not isinstance(detail, Attribute):
                results.append( ('error', "Detail '%s' in cube '%s' is not instance of Attribute" % (measure, self.name)) )

        # 2. check whether dimension attributes are unique

        return results

    def localize(self, locale):
        util.localize_common(self,locale)
        
        attr_locales = locale.get("measures")
        if attr_locales:
            for attrib in self.measures:
                if attrib.name in attr_locales:
                    util.localize_common(attrib, attr_locales[attrib.name])

        attr_locales = locale.get("details")
        if attr_locales:
            for attrib in self.details:
                if attrib.name in attr_locales:
                    util.localize_common(attrib, attr_locales[attrib.name])

    def localizable_dictionary(self):
        locale = {}
        locale.update(util.get_localizable_attributes(self))
        
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

    Attributes:
    	* name: dimension name
    	* label: dimension name that will be displayed (human readable)
    	* levels: list of dimension levels (see: :class:`brewery.cubes.Level`)
    	* hierarchies: list of dimension hierarchies
    	* default_hierarchy_name: name of a hierarchy that will be used when no hierarchy is explicitly specified

    **Defaults**
    
    * If no levels are specified during initialization, then dimension name is considered flat, with
      single attribute.
    * If no hierarchy is specified and levels are specified, then default hierarchy will be created
      from order of levels
    * If no levels are specified, then one level is created, with name `default` and dimension will
      be considered flat

    String representation of a dimension ``str(dimension)`` is equal to dimension name.

    Class is not meant to be mutable.
    """

    def __init__(self, name=None, label=None, levels=None,
                 attributes=None, hierarchy=None, description=None, **desc):
        """Create a new dimension
        """
        self.name = name

        self.label = label
        self.description = description

        # FIXME: make this an OrderedDict
        # If there are not levels, create one default level with one default attribute
        self._levels = {}
        self.level_names = []

        if not levels:
            if not attributes:
                attributes = [self.name]
            level = Level(name="default", dimension=self, attributes=attributes)
            self._levels["default"] = level
            self.level_names.append("default")
        else:
            # FIXME: depreciate levels as dictionary, use only list
            if isinstance(levels, dict):
                for level_name, level_info in levels.items():
                    # FIXME: this is a hack for soon-to-be obsolete level specification
                    info = dict([("name", level_name)] + level_info.items())
                    level = Level(dimension = self, **info)
                    self._levels[level_name] = level
                    self.level_names.append(level_name)
            else: # a tuple/list expected
                for level_info in levels:
                    if isinstance(level_info, basestring):
                        level = Level(dimension=self, name=level_info, attributes=[level_info])
                    else:
                        level = Level(dimension=self, **level_info)

                    self._levels[level.name] = level
                    self.level_names.append(level.name)
        
        hierarchies = desc.get("hierarchies")
        
        if hierarchy and hierarchies:
            raise ModelError("Both 'hierarchy' and 'hierarchies' specified. Use only one")

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
            hier = Hierarchy(dimension=self,name="default", levels=self.level_names)
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

        levels = self.levels
        for level in other.levels:
            if level not in levels:
                return False

        hierarchies = self.hierarchies
        for hier in other.hierarchies:
            if hier not in hierarchies:
                return False

        return True
        
    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def has_details(self):
        """Returns ``True`` when each level has only one attribute, usually key."""

        return any([level.has_details for level in self._levels.values()])

    @property
    def levels(self):
        """Get list of all dimension levels. Order is undefined."""
        return self._levels.values()

    def level(self, obj):
        """Get level by name."""
        if type(obj) == str or type(obj) == unicode:
            if obj not in self._levels:
                raise KeyError("No level %s in dimension %s" % (obj, self.name))
            return self._levels[obj]
        elif type(obj) == Level:
            return obj
        else:
            raise ValueError("Unknown level object %s (should be a string or Level)" % obj)

    @property
    def default_hierarchy(self):
        """Get default hierarchy specified by ``default_hierarchy_name``, if the variable is not set then
        get a hierarchy with name *default*"""
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
                            self._flat_hierarchy = self.flat_hierarchy(self.levels[0])

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

    def flat_hierarchy(self, level):
        """Return the only one hierarchy for the only one level"""
        # if len(levels) > 0:
        #     raise AttributeError("Could not create default flat hierarchy in dimension '%s' if there "
        #                          "are more than one level" % self.name)
        hier = Hierarchy(name = level.name, dimension = self)
        hier.levels = [level.name]
        return hier

    @property
    def is_flat(self):
        """Return true if dimension has only one level"""
        return len(self.levels) == 1

    def attribute_reference(self, attribute, locale=None):
        """Return an Attribute object if it is a string, otherwise just return the object."""
        if isinstance(attribute, basestring):
            attr = Attribute(attribute,locale=locale)
            return attr.full_name(dimension=self)
        else:
            return attribute.full_name(dimension=self)

    def all_attributes(self, hierarchy = None):
        if not hierarchy:
            hier = self.default_hierarchy
        elif type(hierarchy) == str:
            hier = self.hierarchies[hierarchy]
        else:
            hier = hierarchy

        attributes = []
        for level in hier.levels:
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

        skip_hierarchy_check = False
        if not self.levels:
            skip_hierarchy_check = True
            results.append( ('error', "No attributes or levels in dimension '%s'" % (self.name)) )

        if not skip_hierarchy_check:
            if not self.hierarchies:
                base = "No hierarchies in dimension '%s'" % (self.name)
                if self.is_flat:
                    level = self.levels[0]
                    results.append( ('default', base + ", flat level '%s' will be used" % (level.name)) )
                elif len(self.levels) > 1:
                    results.append( ('error', base + ", more than one levels exist (%d)" % len(self.levels)) )
                else:
                    results.append( ('error', base) )
            else:
                if not self.default_hierarchy_name:
                    if len(self.hierarchies) > 1 and not "default" in self.hierarchies:
                        results.append( ('error', "No defaut hierarchy specified, there is "\
                                                  "more than one hierarchy in dimension '%s'" % self.name) )
                    else:
                        def_name = self.default_hierarchy.name
                        results.append( ('default', "No default hierarchy name specified in dimension '%s', using "
                                                    "'%s'"% (self.name, def_name)) )

        if self.default_hierarchy_name and not self.hierarchies.get(self.default_hierarchy_name):
            results.append( ('warning', "Default hierarchy '%s' does not exist in dimension '%s'" % 
                            (self.default_hierarchy_name, self.name)) )

        for level_name, level in self._levels.items():
            if not level.attributes:
                results.append( ('error', "Level '%s' in dimension '%s' has no attributes" % (level.name, self.name)) )
                continue

            if not level._key:
                attr = level.attributes[0]
                results.append( ('default', "Level '%s' in dimension '%s' has no key attribute specified, "\
                                            "first attribute will be used: '%s'" 
                                            % (level.name, self.name, attr)) )

            if level.attributes and level._key:
                found = False
                for attr in level.attributes:
                    if attr.name == level._key:
                        found = True
                        break
                if not found:
                    results.append( ('error', "Key '%s' in level '%s' in dimension '%s' " \
                                              "is not in attribute list"
                                                % (level.key, level.name, self.name)) )

            for attribute in level.attributes:
                if not isinstance(attribute, Attribute):
                    results.append( ('error', "Attribute '%s' in dimension '%s' is not instance of Attribute" % (attribute, self.name)) )
                
        return results

    def __str__(self):
        return self.name
        
    def __repr__(self):
        return "<dimension: {name: '%s', levels: %s}>" % (self.name, self.level_names)
        
    def localize(self, locale):
        util.localize_common(self, locale)

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
        locale.update(util.get_localizable_attributes(self))

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
    """Dimension hierarchy

    Attributes:
        * name: hierarchy name
        * label: human readable name
        * levels: ordered list of levels from dimension
    """

    def __init__(self, name = None, levels = None, label = None, dimension = None):
        self.name = name
        self.label = label
        self.dimension = dimension
        self._levels = OrderedDict()
        self.levels = levels
    
    @property
    def levels(self):
        return self._levels.values()
        
    @levels.setter
    def levels(self, levels):
        self._levels = OrderedDict()
        if levels:
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

    def levels_for_path(self, path, drilldown = False):
        """Returns levels for given path. If path is longer than hierarchy levels, exception is raised"""
        if not path:
            if drilldown:
                return self.levels[0:1]
            else:
                return []

        if drilldown:
            extend = 1
        else:
            extend = 0
        
        if len(path) + extend > len(self.levels):
            raise AttributeError("Path %s is longer than hierarchy levels %s" % (path, self.level_names))

        return self.levels[0:len(path)+extend]

    def next_level(self, level):
        """Returns next level in hierarchy after `level`. If `level` is last level, returns
        ``None``"""

        if isinstance(level, basestring):
            level_name = level
        else:
            level_name = level.name

        index = self._levels.keys().index(level_name)
        if index + 1 == len(self._levels):
            return None
        else:
            return self.levels[index + 1]
        

    def previous_level(self, level):
        """Returns previous level in hierarchy after `level`. If `level` is first level, 
        returns ``Nonte``"""
        
        if isinstance(level, basestring):
            level_name = level
        else:
            level_name = level.name

        index = self._levels.keys().index(level_name)
        if index == 0:
            return None
        else:
            return self.levels[index - 1]

    def rollup(self, path, level = None):
        """Rolls-up the path to the `level`. If `level` is None then path is rolled-up only
        one level. If `level` is deeper than last level of `path` the exception is raised. If 
        `level` is the same as `path` level, nothing happens."""
        
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
        """Returns True if path is base path for the hierarchy. Base path is a path where there are
        no more levels to be added - no drill down possible."""
        
        return path != None and len(path) == len(self._levels)

    def to_dict(self, **options):
        """Convert to dictionary"""

        out = IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("levels", self._levels.keys())

        return out
        
    def localize(self, locale):
        util.localize_common(self,locale)

    def localizable_dictionary(self):
        locale = {}
        locale.update(util.get_localizable_attributes(self))

        return locale

class Level(object):
    """Hierarchy level
    
    Attributes:
        * name: level name
        * label: human readable label 
        * key: key field of the level (customer number for customer level, region code for region level, 
            year-month for month level). key will be used as a grouping field for aggregations. Key should be unique within level.
        * label_attribute: name of attribute containing label to be displayed (customer_name for customer level,
            region_name for region level, month_name for month level)
        * attributes: list of other additional attributes that are related to the level. The attributes are not being used for aggregations, 
            they provide additional useful information
    """
    def __init__(self, name = None, key = None, attributes = None, null_value = None, 
                label = None, label_attribute = None, dimension = None):
        self.name = name
        self.label = label
        self.null_value = null_value
        self._key = key
        self.attributes = attribute_list(attributes)
        self._label_attribute = label_attribute
            
        self.dimension = dimension

    def __eq__(self, other):
        if not other or type(other) != type(self):
            return False
        elif self.name != other.name or self.label != other.label or self._key != other._key:
            return False
        elif self._label_attribute != other._label_attribute:
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

    def to_dict(self, full_attribute_names = False, **options):
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
            array.append(attr.to_dict(dimension = self.dimension, **options))
        out.setnoempty("attributes", array)
        out.setnoempty("label_attribute", self._label_attribute)

        return out

    @property
    def has_details(self):
        return len(self.attributes) > 1

    @property
    def key(self):
        if self._key:
            return self._key
        else:
            return self.attributes[0].name
            
    @property
    def label_attribute(self):
        if self._label_attribute:
            return self._label_attribute
        else:
            if len(self.attributes) > 1:
                return self.attributes[1]
            else:
                return self.key

    def localize(self, locale):
        util.localize_common(self,locale)
        
        attr_locales = locale.get("attributes")
        if attr_locales:
            for attrib in self.attributes:
                if attrib.name in attr_locales:
                    util.localize_common(attrib, attr_locales[attrib.name])

    def localizable_dictionary(self):
        locale = {}
        locale.update(util.get_localizable_attributes(self))

        adict = {}
        locale["attributes"] = adict

        for attribute in self.attributes:
            adict[attribute.name] = attribute.localizable_dictionary()
            
        return locale


def attribute_list(attributes):
    """Create a list of attributes from a list of strings or dictionaries."""

    if not attributes:
        return []
    array = []
    for attr in attributes:
        if type(attr) == str or type(attr) == unicode:
            new = Attribute(name = attr)
        else:
            new = Attribute(**attr)
        array.append(new)
    return array

class Attribute(object):
    """Cube attribute - represents any fact field/column"""
    
    ASC = 'asc'
    DESC = 'desc'
    
    def __init__(self, name, label=None, locales=None, order=None, description=None,
                 **kwargs):
        """Create an attribute.
        
        :Attributes:
            * `name` - attribute name, used as identifier
            * `label` - attribute label displayed to a user
            * `locales` = list of locales that the attribute is localized to
            * `order` - default order of this attribute. If not specified, then order is
              unexpected. Possible values are: ``'asc'``/``'ascending'`` or
              ``'desc'``/``'descending'``. It is recommended and safe to use ``Attribute.ASC`` and
              ``Attribute.DESC``
        
        """
        super(Attribute, self).__init__()
        self.name = name
        self.label = label
        self.description = description
        
        if order:
            self.order = order.lower()
            if self.order == 'ascending':
                self.order = Attribute.ASC
            if self.order == 'descending':
                self.order = Attribute.DESC
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
        if dimension:
            d["full_name"] = self.full_name(dimension)
        return d
        
    def full_name(self, dimension, locale=None):
        """Return full name of an attribute as if it was part of `dimension`. Append `locale` if
        it is one of of attribute's locales, otherwise raise an error.
        """
        # Old behaviour: If no locale is specified and attribute is localized, then first locale from
        # list of locales is used.

        if locale:
            if locale in self.locales:
                raise ValueError("Attribute '%s' has no localization %s" % self.name)
            else:
                locale_suffix = "." + locale
        else:
            locale_suffix = ""

        return str(dimension) + "." + self.name + locale_suffix

    def localizable_dictionary(self):
        locale = {}
        locale.update(util.get_localizable_attributes(self))

        return locale

class Measure(Attribute):
    """Class representing a cube measure."""
    def __init__(self, name, label = None, locales = None, order = None, aggregations = None, **kwargs):
        """Creates a cube measure object. In addition to Attribute object it contains list of
        meaningful aggregations that can be performed on this attribute."""

        super(Measure, self).__init__(name, label, locales, order, **kwargs)
        self.aggregations = aggregations
