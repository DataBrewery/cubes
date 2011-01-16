import cubes.base as base
import os
import re
import urllib2
import urlparse

try:
    import json
except ImportError:
    import simplejson as json

def load_model(resource):
    """Load logical model from object reference. `ref` can be an URL, local file path or file-like
    object."""

    handle = None
    if type(resource) == str or type(resource) == unicode:
        parts = urlparse.urlparse(resource)
        if parts.scheme == '' or parts.scheme == 'file':
            handle = file(resource)
            should_close = True
        else:
            handle = urllib2.urlopen(resource)
            should_close = True
    else:
        handle = resource

    model_desc = json.load(handle)

    if should_close:
        handle.close()

    return model_from_dict(model_desc)

def model_from_url(url):
    """Load logical model from a URL.

    Argrs:
        url: URL with json representation of the model.

    Returs:
        instance of Model

    .. warning::
        Not implemented yet
    """
    handle = urllib2.urlopen(url)
    model_desc = json.load(handle)
    handle.close()
    return model_from_dict(model_desc)

def model_from_path(path):
    """Load logical model from a directory specified by path

    Argrs:
        path: directory where model is located

    Returs:
        instance of Model
    """

    if not os.path.isdir(path):
        a_file = open(path)
        model_desc = json.load(a_file)
        a_file.close()
        return model_from_dict(model_desc)

    info_path = os.path.join(path, 'model.json')

    if not os.path.exists(info_path):
        raise RuntimeError('main model info %s does not exist' % info_path)

    a_file = open(info_path)
    model_desc = json.load(a_file)
    a_file.close()

    if not "name" in model_desc:
        raise KeyError("model has no name")

    # Find model object files and load them

    dimensions_to_load = []
    cubes_to_load = []

    if not "dimensions" in model_desc:
        model_desc["dimensions"] = {}
    elif type(model_desc["dimensions"]) != dict:
        raise ValueError("dimensions object in model file be a dictionary")

    if not "cubes" in model_desc:
        model_desc["cubes"] = {}
    elif type(model_desc["cubes"]) != dict:
        raise ValueError("cubes object in model file should be a dictionary")

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
                    raise KeyError("Dimension file '%s' has no name key" % obj_path)
                model_desc["dimensions"][desc["name"]] = desc
            elif prefix == 'cube':
                desc = _model_desc_from_json_file(obj_path)
                if "name" not in desc:
                    raise KeyError("Cube file '%s' has no name key" % obj_path)
                model_desc["cubes"][desc["name"]] = desc

    return model_from_dict(model_desc)

def model_from_dict(desc):
    """Create a model from description dictionary

    Arguments:
        desc: model dictionary
    """

    model = Model(desc["name"], desc)
    return model

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
    Logical Model represents mapping between human point of view on analysed facts and their physical
    database representation. Main objects of a model are datasets (physical objects) and multidimensioanl
    cubes (logical objects). For more information see Cube.
    """

    def __init__(self, name, desc = {}):
    	self.name = name
    	self.label = desc.get('label','')
    	self.description = desc.get('description','')

    	self._dimensions = {}

    	dimensions = desc.get('dimensions', None)
    	if dimensions:
    	    for dim_name, dim_desc in dimensions.items():
    	        dim = Dimension(dim_name, dim_desc)
                self.add_dimension(dim)

    	self.cubes = {}

    	cubes = desc.get('cubes', None)
    	if cubes:
    	    for cube_name, cube_desc in cubes.items():
                self.create_cube(cube_name, cube_desc)
    	        

    def create_cube(self, cube_name, info ={}):
        """Create a Cube instance for the model. This is designated factory method for cubes as it
        properrely creates references to dimension objects
        
        Args:
            * cube_name: name of a cube to be created
            * info: dict object with cube information

        Returns:
            * freshly created and initialized Cube instance
        """

        cube = Cube(cube_name, info)
        cube.model = self
        self.cubes[cube_name] = cube

    	dims = info.get('dimensions','')
    	
    	if dims and type(dims) == list:
    	    for dim_name in dims:
    	        dim = self.dimension(dim_name)
    	        if not dim:
    	            raise KeyError("There is no dimension '%s' for cube '%s' in model '%s'" % (dim_name, cube_name, self.name))
                cube.add_dimension(dim)

        return cube

    def add_dimension(self, dimension):
        """Add dimension to cube. Replace dimension with same name"""

        # FIXME: Do not allow to add dimension if one already exists
        self._dimensions[dimension.name] = dimension

    def remove_dimension(self, dimension):
        """Remove a dimension from receiver"""
        del self._dimensions[dimension.name]
        # FIXME: check whether the dimension is not used in cubes

    @property
    def dimensions(self):
        return self._dimensions.values()

    def dimension(self, name):
        """Get dimension by name"""
        return self._dimensions[name]

    def to_dict(self):
        """Return dictionary representation of the model. All object references within the dictionary are
        name based"""

        def add_value(d, key, value):
            if value:
                d[key] = value
                
        
        out = base.IgnoringDictionary()

        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("description", self.description)

        dims = {}
        for dim in self.dimensions:
            dims[dim.name] = dim.to_dict()

        out.setnoempty("dimensions", dims)

        cubes = {}
        for cube in self.cubes.values():
            cubes[cube.name] = cube.to_dict()

        out.setnoempty("cubes", cubes)

        return out

    def to_json(self):
        """Return json representation of the model"""
        return json.dumps(self.to_dict())

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
    
class Cube(object):
    """
    OLAP Cube - Logical Representation

    Attributes:
    	* model: logical model
    	* name: cube name
    	* label: name that will be displayed (human readable)
    	* measures: list of fact measures
    	* dimensions: list of fact dimensions
    	* mappings: map logical attributes to physical dataset fields (table columns)
    	* joins
        * fact: dataset containing facts (fact table)
    """

    def __init__(self, name, info = {}):
        """Create a new cube

        Args:
            * name (str): dimension name
            * desc (dict): dict object containing keys label, description, dimensions, ...
        """
        self.name = name

        self.label = info.get("label", "")
        self.description = info.get("description", "")
        self.measures = info.get("measures", [])
        self.attributes = info.get("attributes", [])
        self.model = None
        self._dimensions = {}
        self.mappings = info.get("mappings", {})
        self.fact = info.get("fact", None)
        self.joins = info.get("joins", [])

    def add_dimension(self, dimension):
        """Add dimension to cube. Replace dimension with same name"""

        # FIXME: Do not allow to add dimension if one already exists
        self._dimensions[dimension.name] = dimension
        if self.model:
            self.model.add_dimension(dimension)

    def remove_dimension(self, dimension):
        """Remove a dimension from receiver"""
        del self._dimensions[dimension.name]

    @property
    def dimensions(self):
        return self._dimensions.values()

    def dimension(self, name):
        """Get dimension by name"""
        
        # Fixme: check for existence
        if type(name) == str:
            return self._dimensions[name]
        elif issubclass(name.__class__, Dimension):
             return name
        else:
            raise AttributeError("Invalid dimension or dimension reference '%s' for cube '%s'" %
                                    name, self.name)

    def to_dict(self):
        """Convert to dictionary"""

        out = base.IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("measures", self.measures)

        dims = [dim.name for dim in self.dimensions]

        # Give sorted list so we can nicely compare dictionaries
        out.setnoempty("dimensions", dims.sort())

        out.setnoempty("mappings", self.mappings)
        out.setnoempty("fact", self.fact)
        out.setnoempty("joins", self.joins)

        return out

    def validate(self):
        """Validate cube. See Model.validate() for more information. """
        results = []

        # if not self.mappings:
        #     results.append( ('warning', "No mappings for cube '%s'" % self.name) )

        # if not self.fact:
        #     results.append( ('warning', "No fact specified for cube '%s' (factless cubes are not yet supported, "
        #                                 "using 'fact' as default dataset/table name)" % self.name) )

        # 1. collect all fields(attributes) and check whether there is a mapping for that
        for measure in self.measures:
            try:
                mapping = self.fact_field_mapping(measure)
            except KeyError:
                results.append( ('warning', "No mapping for measure '%s' in cube '%s'" % (measure, self.name)) )

        for dimension in self.dimensions:
            attributes = dimension.all_attributes()
            for attribute in attributes:
                try:
                    mapping = self.dimension_field_mapping(dimension, attribute)
                except KeyError:
                    results.append( ('warning', "No mapping for dimension '%s' attribute '%s' in cube '%s' " \
                                                "(using default mapping)" % (dimension.name, attribute, self.name)) )


        # 2. check whether dimension attributes are unique
        # 3. check whether dimension has valid keys


        # if !fact_dataset
        #     results << [:error, "Unable to find fact dataset '#{fact_dataset_name}' for cube '#{name}'"]
        # end
        # 
        # dimensions.each { | dim |
        #     dim.levels.each { |level|
        #         level.level_fields.each { |field|
        #             ref = field_reference(field)
        #             ds = logical_model.dataset_description_with_name(ref[0])
        #             if !ds
        #                 results << [:error, "Unknown dataset '#{ref[0]}' for field '#{field}', dimension '#{dim.name}', level '#{level.name}', cube '#{name}'"]
        #             else
        #                 fd = ds.field_with_name(ref[1])
        #                 if !fd
        #                     results << [:error, "Unknown dataset field '#{ref[0]}.#{ref[1]}' specified in dimension '#{dim.name}', level '#{level.name}', cube '#{name}'"]
        #                 end
        #             end
        #         }
        #     }
        # }
        # 
        return results

    def measure_mapping(self, measure):
        """Return mapping for a measure"""

        mapped = self.mappings.get(measure)
        if not mapped:
            mapped = self.mappings.get("fact." + measure)

        if not mapped:
            mapped = measure
            # FIXME: raise this on "strict mappings"?
            # raise KeyError("Cube '%s' has no mapping for measure '%s'" % (self.name, measure))

        return mapped

    def dimension_field_mapping(self, dimension, attribute):
        """Return mapping for a dimension attribute. If there is no mapping defined return default mapping where
        table/dataset name is same as dimension name and column/field name is same as dimension attribute

        Return: string
        """

        reference = "%s.%s" % (dimension.name, attribute)
        physical = self.mappings.get(reference)

        # If there is no mapping, use default mapping
        if not physical:
            physical = reference

        return (physical, reference)

    def fact_field_mapping(self, field):
        """Return physical field name"""

        physical = self.mappings.get(field)
        if not physical:
            physical = field

        return (physical, field)

class Dimension(object):
    """
    Cube dimension.

    Attributes:
    	* model: logical model
    	* name: dimension name
    	* label: dimension name that will be displayed (human readable)
    	* levels: list of dimension levels (see: :class:`brewery.cubes.Level`)
    	* hierarchies: list of dimension hierarchies
    	* default_hierarchy_name: name of a hierarchy that will be used when no hierarchy is explicitly specified
    """

    def __init__(self, name, desc = {}):
        """Create a new dimension

        Args:
            * name (str): dimension name
            * desc (dict): dict object containing keys label, description, levels, hierarchies, default_hierarchy, key_field
        """
        self.name = name

        self.label = desc.get("label", "")
        self.description = desc.get("description", "")

        self._levels = []
        self.level_names = []

        self.__init_levels(desc.get("levels", None))
        self.__init_hierarchies(desc.get("hierarchies", None))
        self._flat_hierarchy = None

        self.default_hierarchy_name = desc.get("default_hierarchy", None)
        self.key_field = desc.get("key_field")

    def __eq__(self, other):
        if not other or type(other) != type(self):
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


    def __init_levels(self, desc):
        self._levels = {}

        if desc == None:
            return

        for level_name, level_info in desc.items():
            level = Level(level_name, level_info)
            level.dimension = self
            self._levels[level_name] = level
            self.level_names.append(level_name)

    def __init_hierarchies(self, desc):
        """booo bar"""
        self.hierarchies = {}

        if desc == None:
            return

        for hier_name, hier_info in desc.items():
            hier = Hierarchy(hier_name, hier_info)
            hier.dimension = self
            self.hierarchies[hier_name] = hier

    def _initialize_default_flat_hierarchy(self):
        if not self._flat_hierarchy:
            self._flat_hierarchy = self.flat_hierarchy(self.levels[0])

    @property
    def levels(self):
        """Get list of hierarchy levels (unordered)"""
        return self._levels.values()
    
    def level(self, name):
        """Get level by name."""
        if name not in self._levels:
            raise KeyError("No level %s in dimension %s" % (name, self.name))
        return self._levels[name]

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
                        self._initialize_default_flat_hierarchy()
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
        hier = Hierarchy(level.name)
        hier.level_names = [level.name]
        hier.dimension = self
        return hier

    @property
    def is_flat(self):
        """Return true if dimension has only one level"""
        return len(self.levels) == 1

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

    def to_dict(self):
        """Return dict representation of the dimension"""

        out = base.IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("default_hierarchy_name", self.default_hierarchy_name)

        levels_dict = {}
        for level in self.levels:
            levels_dict[level.name] = level.to_dict()
        out["levels"] = levels_dict

        hier_dict = {}
        for hier in self.hierarchies.values():
            hier_dict[hier.name] = hier.to_dict()
        out["hierarchies"] = hier_dict


    	# * levels: list of dimension levels (see: :class:`brewery.cubes.Level`)
    	# * hierarchies: list of dimension hierarchies

        return out

    def validate(self):
        """Validate dimension. See Model.validate() for more information. """
        results = []

        if not self.levels:
            results.append( ('error', "No levels in dimension '%s'" % (self.name)) )

        if not self.hierarchies:
            base = "No hierarchies in dimension '%s'" % (self.name)
            if self.is_flat:
                level = self.levels[0]
                results.append( ('warning', base + ", flat level '%s' will be used" % (level.name)) )
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
                    results.append( ('warning', "No default hierarchy name specified in dimension '%s', using "
                                                "'%s'"% (self.name, def_name)) )

        if self.default_hierarchy_name and not self.hierarchies.get(self.default_hierarchy_name):
            results.append( ('warning', "Default hierarchy '%s' does not exist in dimension '%s'" % 
                            (self.default_hierarchy_name, self.name)) )

        for level_name, level in self._levels.items():
            if not level.attributes:
                results.append( ('error', "Level '%s' in dimension '%s' has no attributes" % (level.name, self.name)) )
            else:
                if not level._key:
                    attr = level.attributes[0]
                    results.append( ('warning', "Level '%s' in dimension '%s' has no key attribute specified, "\
                                                "first attribute will be used: '%s'" 
                                                % (level.name, self.name, attr)) )

            if level.attributes and level._key and level._key not in level.attributes:
                results.append( ('error', "Key '%s' in level '%s' in dimension '%s' in not in attribute list"
                                                % (level.key, level.name, self.name)) )

        return results

    def __str__(self):
        return "<dimension: {name: '%s', levels: %s}>" % (self.name, self.level_names)
    def __repr__(self):
        return self.__str__()
    
class Hierarchy(object):
    """Dimension hierarchy

    Attributes:
        * name: hierarchy name
        * label: human readable name
        * levels: ordered list of levels from dimension
    """

    def __init__(self, name, info = {}, dimension = None):
        self.name = name
        self._dimension = None
        self.label = info.get("label", "")
        self.level_names = info.get("levels", [])
        self.dimension = dimension
        self.levels = []

    def __eq__(self, other):
        if not other or type(other) != type(self):
            return False
        elif self.name != other.name or self.label != other.label:
            return False
        elif self.levels != other.levels:
            return False
        # elif self._dimension != other._dimension:
        #     return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def dimension(self):
        return self._dimension

    @dimension.setter
    def dimension(self, a_dimension):
        self._dimension = a_dimension
        self.levels = []
        if a_dimension != None:
            for level_name in self.level_names:
                level = self.dimension.level(level_name)
                self.levels.append(level)

    def to_dict(self):
        """Convert to dictionary"""

        out = base.IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("levels", self.level_names)

        return out

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
    def __init__(self, name, desc, dimension = None):
        self.name = name
        self.label = desc.get("label", "")
        self._key = desc.get("key", None)
        self.attributes = desc.get("attributes", [])
        self.label_attribute = desc.get("label_attribute", "")
        self.dimension = dimension

    def __eq__(self, other):
        if not other or type(other) != type(self):
            return False
        elif self.name != other.name or self.label != other.label or self._key != other._key:
            return False
        elif self.label_attribute != other.label_attribute:
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

    def to_dict(self):
        """Convert to dictionary"""

        out = base.IgnoringDictionary()
        out.setnoempty("name", self.name)
        out.setnoempty("label", self.label)
        out.setnoempty("key", self.key)
        out.setnoempty("attributes", self.attributes)
        out.setnoempty("label_attribute", self.label_attribute)

        return out

    @property
    def key(self):
        if self._key:
            return self._key
        else:
            return self.attributes[0]

# class DimensionSelector(tuple):
#     """DimensionSelector - specifies a dimension and level depth to be selected. This is utility
#     class that might be used internally in cube aggregations or aggregation browsers.
#     
#     :Attributes:
#     
#         * `dimension`: dimension object
#         * `levels`: list of levels
#     
#     """
#     def __init__(self, dimension, levels):
#         super(DimensionSelector, self).__init__()
#         self.arg = arg
#         