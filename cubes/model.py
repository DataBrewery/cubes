# -*- coding=utf -*-
"""Logical model."""

import copy

from collections import OrderedDict, defaultdict

from .common import IgnoringDictionary, to_label
from .common import assert_instance, assert_all_instances
from .logging import get_logger
from .errors import *
from .statutils import aggregate_calculator_labels

__all__ = [
    "Model",
    "Cube",
    "Dimension",
    "Hierarchy",
    "Level",
    "AttributeBase",
    "Attribute",
    "Measure",
    "MeasureAggregate",

    "create_cube",
    "create_dimension",
    "create_level",
    "create_attribute",
    "create_measure",
    "create_measure_aggregate",
    "attribute_list",

    "fix_dimension_metadata",
    "fix_level_metadata",
    "fix_attribute_metadata"
]


DEFAULT_RECORD_COUNT_AGGREGATE = {
    "name": "record_count",
    "label": "Count",
    "function": "count"
}


# TODO: make this configurable
IMPLICIT_AGGREGATE_LABELS = {
    "sum": u"Sum of {measure}",
    "count": u"Record Count",
    "count_nonempty": u"Non-empty count of {measure}",
    "min": u"{measure} Minimum",
    "max": u"{measure} Maximum",
    "avg": u"Average of {measure}",
}

IMPLICIT_AGGREGATE_LABELS.update(aggregate_calculator_labels())

_DEFAULT_LEVEL_ROLES = {
    "time": ("year", "quarter", "month", "day", "hour", "minute", "second")
}

class Model(object):
    def __init__(self, name=None, locale=None, label=None, description=None,
                 info=None, mappings=None, provider=None, metadata=None,
                 translations=None):
        """
        Logical representation of data. Base container for cubes and
        dimensions.

        Attributes:

        * `name` - model name
        * `dimensions` - list of `Dimension` instances
        * `locale` - locale code of the model
        * `label` - human readable name - can be used in an application
        * `description` - longer human-readable description of the model
        * `info` - custom information dictionary

        * `metadata` – a dictionary describing the model
        * `provider` – an object that creates model objects

        """
        # * `mappings` – model-wide mappings of logical-to-physical attributes

        # Basic information
        self.name = name
        self.label = label
        self.description = description
        self.locale = locale
        self.info = info or {}
        self.provider = provider
        self.metadata = metadata

        # Physical information
        self.mappings = mappings

        self.translations = translations or {}

    def __str__(self):
        return 'Model(%s)' % self.name

    def to_dict(self, **options):
        """Return dictionary representation of the model. All object
        references within the dictionary are name based

        * `full_attribute_names` - if set to True then attribute names will be
          written as ``dimension_name.attribute_name``
        """

        out = IgnoringDictionary()

        out["name"] = self.name
        out["label"] = self.label
        out["description"] = self.description
        out["info"] = self.info

        if options.get("with_mappings"):
            out["mappings"] = self.mappings

        return out

    def __eq__(self, other):
        if other is None or type(other) != type(self):
            return False
        if self.name != other.name or self.label != other.label \
                or self.description != other.description:
            return False
        elif self.info != other.info:
            return False
        return True

    def _add_translation(self, lang, translation):
        self.translations[lang] = translation

    # TODO: move to separate module
    def localize(self, translation):
        """Return localized version of the model.

        `translation` might be a string or a dicitonary. If it is a string,
        then it represents locale name from model's localizations provided on
        model creation. If it is a dictionary, it should contains full model
        translation that is going to be applied.


        Translation dictionary structure example::

            {
                "locale": "sk",
                "cubes": {
                    "sales": {
                        "label": "Predaje",
                        "measures":
                            {
                                "amount": "suma",
                                "discount": {"label": "zľava",
                                             "description": "uplatnená zľava"}
                            }
                    }
                },
                "dimensions": {
                    "date": {
                        "label": "Dátum"
                        "attributes": {
                            "year": "rok",
                            "month": {"label": "mesiac"}
                        },
                        "levels": {
                            "month": {"label": "mesiac"}
                        }
                    }
                }
            }

        .. note::

            Whenever master model changes, you should call this method to get
            actualized localization of the original model.
        """

        model = copy.deepcopy(self)

        if type(translation) == str or type(translation) == unicode:
            try:
                translation = self.translations[translation]
            except KeyError:
                raise ModelError("Model has no translation for %s" %
                                 translation)

        if "locale" not in translation:
            raise ValueError("No locale specified in model translation")

        model.locale = translation["locale"]
        localize_common(model, translation)

        if "cubes" in translation:
            for name, cube_trans in translation["cubes"].items():
                cube = model.cube(name)
                cube.localize(cube_trans)

        if "dimensions" in translation:
            dimensions = translation["dimensions"]
            for name, dim_trans in dimensions.items():
                # Use translation template if exists, similar to dimension
                # template
                template_name = dim_trans.get("template")

                if False and template_name:
                    try:
                        template = dimensions[template_name]
                    except KeyError:
                        raise ModelError("No translation template '%s' for "
                                "dimension '%s'" % (template_name, name))

                    template = dict(template)
                    template.update(dim_trans)
                    dim_trans = template

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


class ModelObject(object):
    """Base classs for all model objects."""

    def __init__(self, name=None, label=None, description=None, info=None):
        self.name = name
        self.label = label
        self.description = description
        self.info = info


class Cube(object):
    def __init__(self, name, dimensions=None, measures=None, aggregates=None,
                 label=None, details=None, mappings=None, joins=None,
                 fact=None, key=None, description=None, browser_options=None,
                 info=None, linked_dimensions=None,
                 locale=None, category=None, datastore=None,
                 hierarchies=None, **options):

        """Create a new Cube model object.

        Properties:

        * `name`: cube name, used as identifier
        * `measures`: list of measures – numerical attributes
          aggregation functions or natively aggregated values
        * `label`: human readable cube label
        * `details`: list of detail attributes
        * `description` - human readable description of the cube
        * `key`: fact key field (if not specified, then backend default key
          will be used, mostly ``id`` for SLQ or ``_id`` for document based
          databases)
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information
        * `locale`: cube's locale
        * `linked_dimensions` – dimensions to be linked after the cube is
          created
        * `hierarchies` – a dictionary of relevant dimension hierarchies for
          this cube. Keys are dimension names, values are hierarchy names. If
          a dimension is not in this dictionary, then all hierarchies are
          used.

        There are two ways how to assign dimensions to the cube: specify them
        during cube initialization in `dimensions` by providing a list of
        `Dimension` objects. Alternatively you can set `linked_dimensions`
        list with dimension names and the link the dimension using
        :meth:`cubes.Cube.add_dimension()`.

        Physical properties of the cube are described in the following
        attributes. They are used by the backends:

        * `mappings` - backend-specific logical to physical mapping
          dictionary. Keys and values of this dictionary are interpreted by
          the backend.
        * `joins` - backend-specific join specification (used for example in
          the SQL backend). It should be a list of dictionaries.
        * `fact` - fact table (collection, dataset, ...) name
        * `datastore` - name of datastore where the cube belongs
        * `browser_options` - dictionary of other options used by the backend
          - refer to the backend documentation to see what options are used
          (for example SQL browser might look here for ``denormalized_view``
          in case of denormalized browsing)

        """

        self.name = name
        self.locale = locale

        # User-oriented metadata
        self.label = label
        self.description = description
        self.info = info or {}
        # backward compatibility
        self.category = category or self.info.get("category")

        # Physical properties
        self.mappings = mappings
        self.fact = fact
        self.joins = joins
        self.key = key
        self.browser_options = browser_options or {}
        self.datastore = datastore or options.get("datastore")
        self.browser = options.get("browser")

        self.linked_dimensions = linked_dimensions or []
        self.dimension_hierarchies = hierarchies or {}

        # Used by workspace internally
        self.provider = None
        # Used by backends
        self.basename = None

        self._dimensions = OrderedDict()

        if dimensions:
            if all([isinstance(dim, Dimension) for dim in dimensions]):
                for dim in dimensions:
                    self.add_dimension(dim)
            else:
                raise ModelError("Dimensions for cube initialization should be "
                                 "a list of Dimension instances.")
        #
        # Prepare measures and aggregates
        #
        assert_all_instances(measures, Measure, "Measure")
        assert_all_instances(aggregates, MeasureAggregate, "Aggregate")

        # Note: we do not generate aggregates from measure defaults here. We
        # are expected to receive them. They should be generated in the
        # provider.

        self.measures = measure_list(measures)
        self.aggregates = aggregate_list(aggregates)

        self.details = attribute_list(details, Attribute)

    @property
    def measures(self):
        return self._measures.values()

    @measures.setter
    def measures(self, measures):
        self._measures = OrderedDict()
        for measure in measures:
            if measure.name in self._measures:
                raise ModelError("Duplicate measure %s in cube %s" %
                                 (measure.name, self.name))
            self._measures[measure.name] = measure

    @property
    def aggregates(self):
        return self._aggregates.values()

    @aggregates.setter
    def aggregates(self, aggregates):
        self._aggregates = OrderedDict()
        for agg in aggregates:
            if agg.name in self._aggregates:
                raise ModelError("Duplicate aggregate %s in cube %s" %
                                 (agg.name, self.name))

            # TODO: check for conflicts
            self._aggregates[agg.name] = agg

    def aggregates_for_measure(self, name):
        """Returns aggregtates for measure with `name`. Only direct function
        aggregates are returned. If the measure is specified in an expression,
        the aggregate is not included in the returned list"""

        return [agg for agg in self.aggregates if agg.measure == name]

    def get_aggregates(self, names=None):
        """Get a list of aggregates with `names`"""
        if not names:
            return self.aggregates

        return [self._aggregates[str(name)] for name in names]

    def add_dimension(self, dimension):
        """Add dimension to cube. Replace dimension with same name. Raises
        `ModelInconsistencyError` when dimension with same name already exists
        in the receiver. """

        if not isinstance(dimension, Dimension):
            raise ArgumentError("Dimension added to cube '%s' is not a "
                                "Dimension instance." % self.name)

        if dimension.name in self._dimensions:
            raise ModelError("Dimension with name %s already exits "
                             "in cube %s" % (dimension.name, self.name))

        if dimension.name in self.dimension_hierarchies:
            hierarchies = self.dimension_hierarchies[dimension.name]

            if not hierarchies:
                raise ModelInconsistencyError("Can not remove all hierarchies"
                                              "from a dimension. In cube '%s' "
                                              "dimension '%s'"
                                              % (self.name, dimension.name))

            dimension = dimension.limited_clone(hierarchies)


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
        belongs to the cube.

        Raises `NoSuchDimensionError` when there is no such dimension.
        """

        # FIXME: raise better exception if dimension does not exist, but is in
        # the list of required dimensions

        if not obj:
            raise NoSuchDimensionError("Requested dimension should not be none (cube '%s')" % \
                                self.name)

        if isinstance(obj, basestring):
            if obj in self._dimensions:
                return self._dimensions[obj]
            else:
                raise NoSuchDimensionError("cube '%s' has no dimension '%s'" %
                                    (self.name, obj))
        elif isinstance(obj, Dimension):
             return obj
        else:
            raise NoSuchDimensionError("Invalid dimension or dimension "
                                       "reference '%s' for cube '%s'" %
                                            (obj, self.name))

    def measure(self, name):
        """Get measure object. If `obj` is a string, then measure with given
        name is returned, otherwise measure object is returned if it belongs
        to the cube. Returned object is of `Attribute` type.

        Raises `NoSuchAttributeError` when there is no such measure or when
        there are multiple measures with the same name (which also means that
        the model is not valid).
        """

        name = str(name)
        try:
            return self._measures[name]
        except KeyError:
            raise NoSuchAttributeError("cube '%s' has no measure '%s'" %
                                            (self.name, name))

    def measure_aggregate(self, name):
        """Returns a measure aggregate by name."""
        name = str(name)
        try:
            return self._aggregates[name]
        except KeyError:
            raise NoSuchAttributeError("Cube '%s' has no measure aggregate "
                                            "'%s'" % (self.name, name))


    def get_measures(self, measures):
        """Get a list of measures as `Attribute` objects. If `measures` is
        `None` then all cube's measures are returned."""

        array = []

        for measure in measures or self.measures:
            array.append(self.measure(measure))

        return array

    @property
    def all_attributes(self):
        """All cube's attributes from the fact: attributes of dimensions,
        details and measures."""
        attributes = []
        for dim in self.dimensions:
            attributes += dim.all_attributes

        attributes += self.details

        attributes += self.measures

        return attributes

    @property
    def all_aggregate_attributes(self):
        """All cube's attributes for aggregation: attributes of dimensions and
        aggregates.  """

        attributes = []
        for dim in self.dimensions:
            attributes += dim.all_attributes

        attributes += self.aggregates

        return attributes

    def attribute(self, attribute):
        """Returns an attribute object (dimension attribute, measure or
        detail)."""

        for dim in self.dimensions:
            try:
                return dim.attribute(attribute, by_ref=True)
            except KeyError:
                continue

        attrname = str(attribute)
        for detail in self.details:
            if detail.name == attrname:
                return detail

        for measure in self.measures:
            if measure.name == attrname:
                return measure

        raise NoSuchAttributeError("Cube '%s' has no attribute '%s'"
                                   % (self.name, attribute))

    def get_attributes(self, attributes=None, simplify=True, aggregated=False):
        """Returns a list of cube's attributes. If `aggregated` is `True` then
        attributes after aggregation are returned, otherwise attributes for a
        fact are considered.

        Aggregated attributes contain: dimension attributes and aggregates.
        Fact attributes contain: dimension attributes, fact details and fact
        measures.

        If the list `attributes` is empty, all attributes are returned.

        If `simplified_references` is `True` then dimension attribute
        references in `attrubutes` are considered simplified, otherwise they
        are considered as full (dim.attribute)."""

        names = [str(attr) for attr in attributes or []]

        if aggregated:
            attributes = self.all_aggregate_attributes
        else:
            attributes = self.all_attributes

        if not names:
            return attributes

        attr_map = dict((a.ref(simplify), a) for a in attributes)

        result = []
        for name in names:
            try:
                attr = attr_map[name]
            except KeyError:
                raise NoSuchAttributeError("Unknown attribute '%s' in cube "
                                           "'%s'" % (name, self.name))
            result.append(attr)

        return result

    def to_dict(self, expand_dimensions=False, with_mappings=True,
                hierarchy_limits=None, **options):
        """Convert to a dictionary. If `with_mappings` is ``True`` (which is
        default) then `joins`, `mappings`, `fact` and `options` are included.
        Should be set to ``False`` when returning a dictionary that will be
        provided in an user interface or through server API.
        """

        out = IgnoringDictionary()
        out["name"] = self.name
        out["info"] = self.info
        out["category"] = self.category

        if options.get("create_label"):
            out["label"] = self.label or to_label(self.name)
        else:
            out["label"] = self.label

        aggregates = [m.to_dict(**options) for m in self.aggregates]
        out["aggregates"] = aggregates

        measures = [m.to_dict(**options) for m in self.measures]
        out["measures"] = measures

        details = [a.to_dict(**options) for a in self.details]
        out["details"] = details

        if expand_dimensions:
            limits = defaultdict(dict)
            if hierarchy_limits:
                # Convert from (dim,hier,level) to a dict
                for dim, hier, level in hierarchy_limits:
                    limits[dim][hier] = level

            dims = []

            for dim in self.dimensions:
                limit = limits.get(dim.name)
                info = dim.to_dict(hierarchy_limits=limit)
                dims.append(info)

        else:
            dims = [dim.name for dim in self.dimensions]

        out["dimensions"] = dims

        if with_mappings:
            out["mappings"] = self.mappings
            out["fact"] = self.fact
            out["joins"] = self.joins
            out["browser_options"] = self.browser_options

        out["key"] = self.key
        return out

    def __eq__(self, other):
        if other is None or type(other) != type(self):
            return False
        if self.name != other.name or self.label != other.label \
            or self.description != other.description:
            return False
        elif self.dimensions != other.dimensions \
                or self.measures != other.measures \
                or self.aggregates != other.aggregates \
                or self.details != other.details \
                or self.mappings != other.mappings \
                or self.joins != other.joins \
                or self.browser_options != other.browser_options \
                or self.info != other.info:
            return False
        return True

    def validate(self):
        """Validate cube. See Model.validate() for more information. """
        results = []

        # Check whether all attributes, measures and keys are Attribute objects
        # This is internal consistency chceck

        measures = set()

        for measure in self.measures:
            if not isinstance(measure, Attribute):
                results.append(('error',
                                 "Measure '%s' in cube '%s' is not instance"
                                 "of Attribute" % (measure, self.name)))
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
        # FIXME: this needs revision/testing – it might be broken
        localize_common(self,locale)

        attr_locales = locale.get("measures")
        if attr_locales:
            for attrib in self.measures:
                if attrib.name in attr_locales:
                    localize_common(attrib, attr_locales[attrib.name])

        attr_locales = locale.get("aggregates")
        if attr_locales:
            for attrib in self.aggregates:
                if attrib.name in attr_locales:
                    localize_common(attrib, attr_locales[attrib.name])

        attr_locales = locale.get("details")
        if attr_locales:
            for attrib in self.details:
                if attrib.name in attr_locales:
                    localize_common(attrib, attr_locales[attrib.name])

    def localizable_dictionary(self):
        # FIXME: this needs revision/testing – it might be broken
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

    def __str__(self):
        return self.name


class Dimension(object):
    """
    Cube dimension.

    """
    special_roles = ["time"]

    def __init__(self, name, levels, hierarchies=None,
                 default_hierarchy_name=None, label=None, description=None,
                 info=None, role=None, cardinality=None, category=None, **desc):

        """Create a new dimension

        Attributes:

        * `name`: dimension name
        * `levels`: list of dimension levels (see: :class:`cubes.Level`)
        * `hierarchies`: list of dimension hierarchies. If no hierarchies are
          specified, then default one is created from ordered list of `levels`.
        * `default_hierarchy_name`: name of a hierarchy that will be used when
          no hierarchy is explicitly specified
        * `label`: dimension name that will be displayed (human readable)
        * `description`: human readable dimension description
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information (icon, color, ...)
        * `role` – one of recognized special dimension types. Currently
          supported is only ``time``.
        * `cardinality` – cardinality of the dimension members. Used
          optionally by the backends for load protection and frontends for
          better auto-generated front-ends. See :class:`Level` for more
          information, as this attribute is inherited by the levels, if not
          specified explicitly in the level.
        * `category` – logical dimension group (user-oriented metadata)

        Dimension class is not meant to be mutable. All level attributes will
        have new dimension assigned.

        Note that the dimension will claim ownership of levels and their
        attributes. You should make sure that you pass a copy of levels if you
        are cloning another dimension.


        Note: The hierarchy will be owned by the dimension.
        """

        self.name = name

        self.label = label
        self.description = description
        self.info = info or {}
        self.role = role
        self.cardinality = cardinality
        self.category = category

        if not levels:
            raise ModelError("No levels specified for dimension %s"
                             % self.name)

        self._set_levels(levels)

        if hierarchies:
            self.hierarchies = dict((hier.name, hier) for hier in hierarchies)
            # Own the hierarchy
            for hier in hierarchies:
                hier.set_dimension(self)
        else:
            hier = Hierarchy("default", self.levels)
            self.hierarchies = {"default": hier}

        # Claim ownership of hierarchies
        for hier in self.hierarchies.values():
            hier.dimension = self

        self._flat_hierarchy = None
        self.default_hierarchy_name = default_hierarchy_name

        # FIXME: is this needed anymore?
        self.key_field = desc.get("key_field")

    def _set_levels(self, levels):
        """Set dimension levels. `levels` should be a list of `Level`
        instances."""

        self._levels = OrderedDict()
        self._attributes = OrderedDict()
        self._attributes_by_ref = OrderedDict()

        default_roles = _DEFAULT_LEVEL_ROLES.get(self.role)

        for level in levels:
            self._levels[level.name] = level
            if default_roles and level.name in default_roles:
                level.role = level.name

        # Collect attributes
        self._attributes = OrderedDict()
        for level in self.levels:
            for a in level.attributes:
                a.dimension = self
                self._attributes[a.name] = a
                self._attributes_by_ref[a.ref()] = a

    def __eq__(self, other):
        if other is None or type(other) != type(self):
            return False
        if self.name != other.name \
                or self.role != other.role \
                or self.label != other.label \
                or self.description != other.description \
                or self.cardinality != other.cardinality \
                or self.category != other.category:
            return False

        elif self._default_hierarchy() != other._default_hierarchy():
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
                raise KeyError("No level %s in dimension %s" %
                               (obj, self.name))
            return self._levels[obj]
        elif isinstance(obj, Level):
            return obj
        else:
            raise ValueError("Unknown level object %s (should be a string "
                             "or Level)" % obj)

    def hierarchy(self, obj=None):
        """Get hierarchy object either by name or as `Hierarchy`. If `obj` is
        ``None`` then default hierarchy is returned."""

        if obj is None:
            return self._default_hierarchy()
        if isinstance(obj, basestring):
            if obj not in self.hierarchies:
                raise ModelError("No hierarchy %s in dimension %s" %
                                 (obj, self.name))
            return self.hierarchies[obj]
        elif isinstance(obj, Hierarchy):
            return obj
        else:
            raise ValueError("Unknown hierarchy object %s (should be a "
                             "string or Hierarchy instance)" % obj)

    def attribute(self, reference, by_ref=False):
        """Get dimension attribute from `reference`."""
        if by_ref:
            return self._attributes_by_ref[str(reference)]
        else:
            try:
                return self._attributes[str(reference)]
            except KeyError:
                raise NoSuchAttributeError("Unknown attribute '%s' "
                                           "in dimension '%s'"
                                           % (str(reference), self.name),
                                           str(reference))

    def _default_hierarchy(self):
        """Get default hierarchy specified by ``default_hierarchy_name``, if
        the variable is not set then get a hierarchy with name *default*"""

        if self.default_hierarchy_name:
            hierarchy_name = self.default_hierarchy_name
        else:
            hierarchy_name = "default"

        hierarchy = self.hierarchies.get(hierarchy_name)

        if not hierarchy:
            if len(self.hierarchies) == 1:
                hierarchy = self.hierarchies.values()[0]
            elif not self.hierarchies:
                if len(self.levels) == 1:
                    if not self._flat_hierarchy:
                        self._flat_hierarchy = Hierarchy(name=level.name,
                                                         dimension=self,
                                                         levels=[levels[0]])

                    return self._flat_hierarchy
                elif len(self.levels) > 1:
                    raise ModelError("There are no hierarchies in dimenson %s "
                                     "and there are more than one level" %
                                     self.name)
                else:
                    raise ModelError("There are no hierarchies in dimenson "
                                     "%s and there are no levels to make "
                                     "hierarchy from" % self.name)
            else:
                raise ModelError("No default hierarchy specified in dimension"
                                 " '%s' and there is more (%d) than one "
                                 "hierarchy defined" %
                                 (self.name, len(self.hierarchies)))

        return hierarchy

    @property
    def is_flat(self):
        """Is true if dimension has only one level"""
        return len(self.levels) == 1

    def key_attributes(self):
        """Return all dimension key attributes, regardless of hierarchy. Order
        is not guaranteed, use a hierarchy to have known order."""

        return [level.key for level in self._levels.values()]

    @property
    def all_attributes(self):
        """Return all dimension attributes regardless of hierarchy. Order is
        not guaranteed, use :meth:`cubes.Hierarchy.all_attributes` to get
        known order. Order of attributes within level is preserved."""

        return list(self._attributes.values())

    def limited_clone(self, hierarchies):
        """Returns a shallow copy of the receiver and limit hierarchies only
        to those specified in `hierarchies`. If default hierarchy name is not
        in the new hierarchy list, then the first hierarchy from the list is
        used."""

        limited_hiers = []

        for name in hierarchies:
            limited_hiers.append(self.hierarchy(name))

        if self.default_hierarchy_name in hierarchies:
            default_hier = self.default_hierarchy_name
        else:
            default_hier = hierarchies[0]

        levels = []
        seen = set()

        # Get only levels used in the hierarchies
        for hier in limited_hiers:
            for level in hier.levels:
                if level.name in seen:
                    continue

                levels.append(level)
                seen.add(level.name)

        return Dimension(name=self.name,
                         levels=levels,
                         hierarchies=limited_hiers,
                         default_hierarchy_name=default_hier,
                         label=self.label,
                         description=self.description,
                         info=self.info,
                         role=self.role,
                         cardinality=self.cardinality,
                         group=self.group)

    def to_dict(self, hierarchy_limits=None, **options):
        """Return dictionary representation of the dimension"""

        out = IgnoringDictionary()
        out["name"] = self.name
        out["info"] = self.info
        out["default_hierarchy_name"] = self.hierarchy().name
        out["role"] = self.role
        out["cardinality"] = self.cardinality
        out["category"] = self.category

        if options.get("create_label"):
            out["label"] = self.label or to_label(self.name)
        else:
            out["label"] = self.label

        out["levels"] = [level.to_dict(**options) for level in self.levels]

        # Collect hierarchies and apply hierarchy depth restrictions
        hierarchies = []
        hierarchy_limits = hierarchy_limits or {}
        for name, hierarchy in self.hierarchies.items():
            if name in hierarchy_limits:
                level = hierarchy_limits[name]
                if level:
                    depth = hierarchy.level_index(level) + 1
                    restricted = hierarchy.to_dict(depth=depth, **options)
                    hierarchies.append(restricted)
                else:
                    # we ignore the hierarchy
                    pass
            else:
                hierarchies.append(hierarchy.to_dict(**options))

        out["hierarchies"] = hierarchies

        # Use only for reading, during initialization these keys are ignored,
        # as they are derived
        # They are provided here for convenience.
        out["is_flat"] = self.is_flat
        out["has_details"] = self.has_details

        return out

    def validate(self):
        """Validate dimension. See Model.validate() for more information. """
        results = []

        if not self.levels:
            results.append(('error', "No levels in dimension '%s'"
                            % (self.name)))
            return results

        if not self.hierarchies:
            msg = "No hierarchies in dimension '%s'" % (self.name)
            if self.is_flat:
                level = self.levels[0]
                results.append(('default',
                                msg + ", flat level '%s' will be used" %
                                      (level.name)))
            elif len(self.levels) > 1:
                results.append(('error',
                                msg + ", more than one levels exist (%d)" %
                                      len(self.levels)))
            else:
                results.append(('error', msg))
        else:  # if self.hierarchies
            if not self.default_hierarchy_name:
                if len(self.hierarchies) > 1 and \
                        not "default" in self.hierarchies:
                    results.append(('error',
                                    "No defaut hierarchy specified, there is "
                                    "more than one hierarchy in dimension "
                                    "'%s'" % self.name))

        if self.default_hierarchy_name \
                and not self.hierarchies.get(self.default_hierarchy_name):
            results.append(('error',
                            "Default hierarchy '%s' does not exist in "
                            "dimension '%s'" %
                            (self.default_hierarchy_name, self.name)))

        attributes = set()
        first_occurence = {}

        for level_name, level in self._levels.items():
            if not level.attributes:
                results.append(('error',
                                "Level '%s' in dimension '%s' has no "
                                "attributes" % (level.name, self.name)))
                continue

            if not level.key:
                attr = level.attributes[0]
                results.append(('default',
                                "Level '%s' in dimension '%s' has no key "
                                "attribute specified, first attribute will "
                                "be used: '%s'"
                                % (level.name, self.name, attr)))

            if level.attributes and level.key:
                if level.key.name not in [a.name for a in level.attributes]:
                    results.append(('error',
                                    "Key '%s' in level '%s' in dimension "
                                    "'%s' is not in level's attribute list"
                                    % (level.key, level.name, self.name)))

            for attribute in level.attributes:
                attr_name = attribute.ref()
                if attr_name in attributes:
                    first = first_occurence[attr_name]
                    results.append(('error',
                                    "Duplicate attribute '%s' in dimension "
                                    "'%s' level '%s' (also defined in level "
                                    "'%s')" % (attribute, self.name,
                                               level_name, first)))
                else:
                    attributes.add(attr_name)
                    first_occurence[attr_name] = level_name

                if not isinstance(attribute, Attribute):
                    results.append(('error',
                                    "Attribute '%s' in dimension '%s' is "
                                    "not instance of Attribute"
                                    % (attribute, self.name)))

                if attribute.dimension is not self:
                    results.append(('error',
                                    "Dimension (%s) of attribute '%s' does "
                                    "not match with owning dimension %s"
                                    % (attribute.dimension, attribute,
                                       self.name)))

        return results

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<dimension: {name: '%s', levels: %s}>" % (self.name,
                                                          self._levels.keys())

    def localize(self, locale):
        localize_common(self, locale)

        attr_locales = locale.get("attributes", {})

        for attrib in self.all_attributes:
            if attrib.name in attr_locales:
                localize_common(attrib, attr_locales[attrib.name])

        level_locales = locale.get("levels") or {}
        for level in self.levels:
            level_locale = level_locales.get(level.name)
            if level_locale:
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
    * `dimension`: dimension the hierarchy belongs to
    * `label`: human readable name
    * `levels`: ordered list of levels or level names from `dimension`
    * `info` - custom information dictionary, might be used to store
      application/front-end specific information

    Some collection operations might be used, such as ``level in hierarchy``
    or ``hierarchy[index]``. String value ``str(hierarchy)`` gives the
    hierarchy name.

    """
    def __init__(self, name, levels, dimension=None, label=None, info=None):
        self.name = name
        self.label = label
        self.info = info or {}

        # if not dimension:
        #     raise ModelInconsistencyError("No dimension specified for "
        #                                   "hierarchy %s" % self.name)
        self._level_refs = levels
        self._levels = None

        if dimension:
            self.dimension = dimension
            self._set_levels(levels)

    def _set_levels(self, levels):
        if not levels:
            raise ModelInconsistencyError("Hierarchy level list should not be "
                                          "empty (in %s)" % self.name)

        self._levels = OrderedDict()
        for level in levels:
            level = self.dimension.level(level)
            self._levels[level.name] = level

    def set_dimension(self, dimension):
        self.dimension = dimension
        self._set_levels(self._level_refs)

    @property
    def levels(self):
        if not self._levels:
            self._set_levels(self._level_refs)

        return self._levels.values()

    @property
    def level_names(self):
        return self._levels.keys()

    @property
    def levels_dict(self):
        if not self._levels:
            self._set_levels(self._level_refs)

        return self._levels

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
        try:
            return self.levels[item]
        except IndexError:
            raise HierarchyError("Hierarchy '%s' has only %d levels, "
                                 "asking for deeper level"
                                 % (self.name, len(self._levels)))

    def __contains__(self, item):
        if item in self.levels:
            return True
        return item in [level.name for level in self.levels]

    def levels_for_path(self, path, drilldown=False):
        """Returns levels for given path. If path is longer than hierarchy
        levels, `cubes.ArgumentError` exception is raised"""

        depth = 0 if not path else len(path)
        return self.levels_for_depth(depth, drilldown)

    def levels_for_depth(self, depth, drilldown=False):
        """Returns levels for given `depth`. If `path` is longer than
        hierarchy levels, `cubes.ArgumentError` exception is raised"""

        depth = depth or 0
        extend = 1 if drilldown else 0

        if depth + extend > len(self.levels):
            raise HierarchyError("Depth %d is longer than hierarchy "
                                 "levels %s (drilldown: %s)" %
                                 (depth, self._levels.keys(), drilldown))

        return self.levels[0:depth + extend]

    def next_level(self, level):
        """Returns next level in hierarchy after `level`. If `level` is last
        level, returns ``None``. If `level` is ``None``, then the first level
        is returned."""

        if not level:
            return self.levels[0]

        index = self.levels_dict.keys().index(str(level))
        if index + 1 >= len(self.levels):
            return None
        else:
            return self.levels[index + 1]

    def previous_level(self, level):
        """Returns previous level in hierarchy after `level`. If `level` is
        first level or ``None``, returns ``None``"""

        if level is None:
            return None

        index = self.levels_dict.keys().index(str(level))
        if index == 0:
            return None
        else:
            return self.levels[index - 1]

    def level_index(self, level):
        """Get order index of level. Can be used for ordering and comparing
        levels within hierarchy."""
        try:
            return self.levels_dict.keys().index(str(level))
        except ValueError:
            raise HierarchyError("Level %s is not part of hierarchy %s"
                                 % (str(level), self.name))

    def is_last(self, level):
        """Returns `True` if `level` is last level of the hierarchy."""

        return level == self.levels[-1]

    def rollup(self, path, level=None):
        """Rolls-up the path to the `level`. If `level` is ``None`` then path
        is rolled-up only one level.

        If `level` is deeper than last level of `path` the
        `cubes.HierarchyError` exception is raised. If `level` is the same as
        `path` level, nothing happens."""

        if level:
            last = self.level_index(level) + 1
            if last > len(path):
                raise HierarchyError("Can not roll-up: level '%s' in "
                                     "dimension '%s' is deeper than deepest "
                                     "element of path %s" %
                                     (str(level), self.dimension.name, path))
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

        return path is not None and len(path) == len(self.levels)

    def key_attributes(self):
        """Return all dimension key attributes as a single list."""

        return [level.key for level in self.levels]

    @property
    def all_attributes(self):
        """Return all dimension attributes as a single list."""

        attributes = []
        for level in self.levels:
            attributes.extend(level.attributes)

        return attributes

    def to_dict(self, depth=None, **options):
        """Convert to dictionary. Keys:

        * `name`: hierarchy name
        * `label`: human readable label (localizable)
        * `levels`: level names

        """

        out = IgnoringDictionary()

        out["name"] = self.name
        levels = [str(l) for l in self.levels]

        if depth:
            out["levels"] = levels[0:depth]
        else:
            out["levels"] = levels
        out["info"] = self.info

        if options.get("create_label"):
            out["label"] = self.label or to_label(self.name)
        else:
            out["label"] = self.label

        return out

    def localize(self, locale):
        localize_common(self, locale)

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        return locale


class Level(object):
    """Object representing a hierarchy level. Holds all level attributes.

    This object is immutable, except localization. You have to set up all
    attributes in the initialisation process.

    Attributes:

    * `name`: level name
    * `dimension`: dimnesion the level is associated with
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
    * `label_attribute`: name of attribute containing label to be displayed
      (for example: ``customer_name`` for customer level, ``region_name`` for
      region level, ``month_name`` for month level)
    * `label`: human readable label of the level
    * `role`: role of the level within a special dimension
    * `info`: custom information dictionary, might be used to store
      application/front-end specific information
    * `cardinality` – approximation of the number of level's members. Used
      optionally by backends and front ends.

    Cardinality values:

    * ``tiny`` – few values, each value can have it's representation on the
      screen, recommended: up to 5.
    * ``low`` – can be used in a list UI element, recommended 5 to 50 (if sorted)
    * ``medium`` – UI element is a search/text field, recommended for more than 50
      elements
    * ``high`` – backends might refuse to yield results without explicit
      pagination or cut through this level.

    """

    def __init__(self, name, attributes, dimension=None, key=None,
                 order_attribute=None, order=None, label_attribute=None,
                 label=None, info=None, cardinality=None, role=None):

        self.name = name
        self.dimension = dimension
        self.cardinality = cardinality
        self.label = label
        self.info = info or {}
        self.role = role

        if not attributes:
            raise ModelError("Attribute list should not be empty")

        self.attributes = attribute_list(attributes)

        # TODO: don't do this
        # NOTE: Affected by removal: mapper (mostly in SQL)
        for attribute in self.attributes:
            attribute.dimension = dimension

        if key:
            self.key = self.attribute(key)
        elif len(self.attributes) >= 1:
            self.key = self.attributes[0]
        else:
            raise ModelInconsistencyError("Attribute list should not be empty")

        # Set second attribute to be label attribute if label attribute is not
        # set. If dimension is flat (only one attribute), then use the only
        # key attribute as label.

        if label_attribute:
            self.label_attribute = self.attribute(label_attribute)
        else:
            if len(self.attributes) > 1:
                self.label_attribute = self.attributes[1]
            else:
                self.label_attribute = self.key

        # Set first attribute to be order attribute if order attribute is not
        # set

        if order_attribute:
            try:
                self.order_attribute = self.attribute(order_attribute)
            except NoSuchAttributeError:
                raise NoSuchAttributeError("Unknown order attribute %s in "
                                           "dimension %s, level %s" %
                                           (order_attribute,
                                            str(self.dimension), self.name))
        else:
            self.order_attribute = self.attributes[0]

        self.order = order

        self.cardinality = cardinality

    def __eq__(self, other):
        if not other or type(other) != type(self):
            return False
        elif self.name != other.name \
                or self.label != other.label \
                or self.key != other.key \
                or self.cardinality != other.cardinality \
                or self.role != other.role \
                or self.label_attribute != other.label_attribute \
                or self.order_attribute != other.order_attribute \
                or self.attributes != other.attributes:
            return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self.to_dict())

    def __deepcopy__(self, memo):
        if self.order_attribute:
            order_attribute = str(self.order_attribute)
        else:
            order_attribute = None

        return Level(self.name,
                     attributes=copy.deepcopy(self.attributes, memo),
                     key=self.key.name,
                     order_attribute=order_attribute,
                     order=self.order,
                     label_attribute=self.label_attribute.name,
                     info=copy.copy(self.info),
                     label=copy.copy(self.label),
                     cardinality=self.cardinality,
                     role=self.role
                     )

    def to_dict(self, full_attribute_names=False, **options):
        """Convert to dictionary"""

        out = IgnoringDictionary()
        out["name"] = self.name
        out["role"] = self.role
        out["info"] = self.info

        if options.get("create_label"):
            out["label"] = self.label or to_label(self.name)
        else:
            out["label"] = self.label

        if full_attribute_names:
            out["key"] = self.key.ref()
            out["label_attribute"] = self.label_attribute.ref()
            out["order_attribute"] = self.order_attribute.ref()
        else:
            out["key"] = self.key.name
            out["label_attribute"] = self.label_attribute.name
            out["order_attribute"] = self.order_attribute.name

        out["order"] = self.order
        out["cardinality"] = self.cardinality

        out["attributes"] = [attr.to_dict(**options) for attr in
                             self.attributes]
        return out

    def attribute(self, name):
        """Get attribute by `name`"""

        attrs = [attr for attr in self.attributes if attr.name == name]

        if attrs:
            return attrs[0]
        else:
            raise NoSuchAttributeError(name)

    @property
    def has_details(self):
        """Is ``True`` when level has more than one attribute, for all levels
        with only one attribute it is ``False``."""

        return len(self.attributes) > 1

    def localize(self, locale):
        localize_common(self, locale)

        if isinstance(locale, basestring):
            return

        attr_locales = locale.get("attributes")
        if attr_locales:
            logger = get_logger()
            logger.warn("'attributes' in localization dictionary of levels "
                        "is depreciated. Use list of `attributes` in "
                        "localization of dimension")

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


class AttributeBase(object):
    ASC = 'asc'
    DESC = 'desc'

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, missing_value=None, **kwargs):
        """Base class for dimension attributes, measures and measure
        aggregates.

        Attributes:

        * `name` - attribute name, used as identifier
        * `label` - attribute label displayed to a user
        * `order` - default order of this attribute. If not specified, then
          order is unexpected. Possible values are: ``'asc'`` or ``'desc'``.
          It is recommended and safe to use ``Attribute.ASC`` and
          ``Attribute.DESC``
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information
        * `format` - application-specific display format information, useful
          for formatting numeric values of measure attributes
        * `missing_value` – value to be used when there is no value (``NULL``)
          in the data source. Support of this attribute property depends on the
          backend. Please consult the backend documentation for more
          information.

        String representation of the `AttributeBase` returns its `name`.

        `cubes.ArgumentError` is raised when unknown ordering type is
        specified.
        """
        self.name = name
        self.label = label
        self.description = description
        self.info = info or {}
        self.format = format
        self.missing_value = missing_value
        # TODO: temporarily preserved, this should be present only in
        # Attribute object, not all kinds of attributes
        self.dimension = None

        if order:
            self.order = order.lower()
            if self.order.startswith("asc"):
                self.order = Attribute.ASC
            elif self.order.startswith("desc"):
                self.order = Attribute.DESC
            else:
                raise ArgumentError("Unknown ordering '%s' for attributes"
                                    " '%s'" % (order, self.ref()))
        else:
            self.order = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return repr(self.to_dict())

    def __eq__(self, other):
        if not isinstance(other, AttributeBase):
            return False

        # TODO: should we be this strict?
        return self.name == other.name \
            and self.label == other.label \
            and self.info == other.info \
            and self.description == other.description \
            and self.format == other.format \
            and self.missing_value == other.missing_value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.ref())

    def to_dict(self, **options):
        # Use ordered dict for nicer JSON output
        d = IgnoringDictionary()
        d["name"] = self.name

        if options.get("create_label"):
            d["label"] = self.label or to_label(self.name)
        else:
            d["label"] = self.label

        d["description"] = self.description
        d["info"] = self.info
        d["format"] = self.format
        d["order"] = self.order
        d["missing_value"] = self.missing_value

        d["ref"] = self.ref()

        return d

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        return locale

    def is_localizable(self):
        return False

    def ref(self, simplify=None, locale=None):
        return self.name


class Attribute(AttributeBase):

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, dimension=None, locales=None,
                 missing_value=None, **kwargs):
        """Dimension attribute object. Also used as fact detail.

        Attributes:

        * `name` - attribute name, used as identifier
        * `label` - attribute label displayed to a user
        * `locales` = list of locales that the attribute is localized to
        * `order` - default order of this attribute. If not specified, then
          order is unexpected. Possible values are: ``'asc'`` or ``'desc'``.
          It is recommended and safe to use ``Attribute.ASC`` and
          ``Attribute.DESC``
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information
        * `format` - application-specific display format information, useful
          for formatting numeric values of measure attributes

        String representation of the `Attribute` returns its `name` (without
        dimension prefix).

        `cubes.ArgumentError` is raised when unknown ordering type is
        specified.
        """

        super(Attribute, self).__init__(name=name, label=label,
                                        description=description, order=order,
                                        info=info, format=format,
                                        missing_value=missing_value)

        self.dimension = dimension
        self.locales = locales or []

    def __deepcopy__(self, memo):
        return Attribute(self.name,
                         self.label,
                         dimension=self.dimension,
                         locales=copy.deepcopy(self.locales, memo),
                         order=copy.deepcopy(self.order, memo),
                         description=self.description,
                         info=copy.deepcopy(self.info, memo),
                         format=self.format,
                         missing_value=self.missing_value)

    def __eq__(self, other):
        if not super(Attribute, self).__eq__(other):
            return False

        return str(self.dimension) == str(other.dimension) \
               and self.locales == other.locales

    def to_dict(self, **options):
        # FIXME: Depreciated key "full_name" in favour of "ref"
        d = super(Attribute, self).to_dict(**options)

        d["locales"] = self.locales

        return d

    def ref(self, simplify=True, locale=None):
        """Return full attribute reference. Append `locale` if it is one of
        attribute's locales, otherwise raise `cubes.ArgumentError`. If
        `simplify` is ``True``, then reference to an attribute of flat
        dimension without details will be just the dimension name.
        """
        if locale:
            if not self.locales:
                raise ArgumentError("Attribute '%s' is not loalizable "
                                    "(localization %s requested)"
                                    % (self.name, locale))
            elif locale not in self.locales:
                raise ArgumentError("Attribute '%s' has no localization %s "
                                    "(has: %s)"
                                    % (self.name, locale, self.locales))
            else:
                locale_suffix = "." + locale
        else:
            locale_suffix = ""

        if self.dimension:
            if simplify and (self.dimension.is_flat
                             and not self.dimension.has_details):
                reference = self.dimension.name
            else:
                reference = self.dimension.name + '.' + str(self.name)
        else:
            reference = str(self.name)

        return reference + locale_suffix

    def is_localizable(self):
        return bool(self.locales)


def create_measure(md):
    """Create a measure object from metadata."""
    if isinstance(md, basestring):
        md = {"name": md}

    if not "name" in md:
        raise ModelError("Measure has no name.")

    md = dict(md)
    if "aggregations" in md:
        md["aggregates"] = md.pop("aggregations")

    return Measure(**md)


# TODO: give it a proper name
class Measure(AttributeBase):

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, missing_value=None, aggregates=None,
                 formula=None, expression=None, **kwargs):
        """Fact measure attribute.

        Properties:

        * `formula` – name of a formula for the measure
        * `aggregates` – list of default (relevant) aggregate functions that
          can be applied to this measure attribute.

        Note that if the `formula` is specified, it should not refer to any
        other measure that refers to this one (no circular reference).

        The `aggregates` is an optional property and is used for:
        * measure aggergate object preparation
        * optional validation

        String representation of a `Measure` returns its `name`.
        """
        super(Measure, self).__init__(name=name, label=label,
                                      description=description, order=order,
                                      info=info, format=format, missing_value=None)

        self.expression = expression
        self.formula = formula
        self.aggregates = aggregates

    def __deepcopy__(self, memo):
        return Measure(self.name, self.label,
                       order=copy.deepcopy(self.order, memo),
                       description=self.description,
                       info=copy.deepcopy(self.info, memo),
                       format=self.format,
                       missing_value=self.missing_value,
                       aggregates=self.aggregates,
                       expression=self.expression,
                       formula=self.formula)

    def __eq__(self, other):
        if not super(Measure, self).__eq__(other):
            return False

        return self.aggregates == other.aggregates \
               and self.formula == other.formula

    def to_dict(self, **options):
        d = super(Measure, self).to_dict(**options)
        d["formula"] = self.formula
        d["aggregates"] = self.aggregates
        d["expression"] = self.expression

        return d

    def default_aggregates(self):
        """Creates default measure aggregates from a list of receiver's
        measures. This is just a convenience function, correct models should
        contain explicit list of aggregates. If no aggregates are specified,
        then the only aggregate `sum` is assumed.
        """

        aggregates = []

        for agg in (self.aggregates or ["sum"]):
            if agg == "identity":
                name = u"%s" % self.name
                measure = None
                function = None
            else:
                name = u"%s_%s" % (self.name, agg)
                measure = self.name
                function = agg

            aggregate = MeasureAggregate(name=name,
                                         label=None,
                                         description=self.description,
                                         order=self.order,
                                         info=self.info,
                                         format=self.format,
                                         measure=measure,
                                         function=function)

            aggregate.label = _measure_aggregate_label(aggregate, self)
            aggregates.append(aggregate)

        return aggregates


def create_measure_aggregate(md):
    if isinstance(md, basestring):
        md = {"name": md}

    if not "name" in md:
        raise ModelError("Measure aggregate has no name.")

    return MeasureAggregate(**md)


class MeasureAggregate(AttributeBase):

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, missing_value=None, measure=None,
                 function=None, formula=None, expression=None, **kwargs):
        """Masure aggregate

        Attributes:

        * `function` – aggregation function for the measure
        * `formula` – name of a formula that contains the arithemtic
          expression (optional)
        * `measure` – measure name for this aggregate (optional)
        * `expression` – arithmetic expression (only if bacend supported)
        """

        super(MeasureAggregate, self).__init__(name=name, label=label,
                                               description=description,
                                               order=order, info=info,
                                               format=format,
                                               missing_value=missing_value)

        self.function = function
        self.formula = formula
        self.expression = expression
        self.measure = measure

    def __deepcopy__(self, memo):
        return MeasureAggregate(self.name,
                                self.label,
                                order=copy.deepcopy(self.order, memo),
                                description=self.description,
                                info=copy.deepcopy(self.info, memo),
                                format=self.format,
                                missing_value=self.missing_value,
                                measure=self.measure,
                                function=self.function,
                                formula=self.formula,
                                expression=self.expression)

    def __eq__(self, other):
        if not super(Attribute, self).__eq__(other):
            return False

        return str(self.function) == str(other.function) \
            and self.measure == other.measure \
            and self.formula == other.formula \
            and self.expression == other.expression

    def to_dict(self, **options):
        d = super(MeasureAggregate, self).to_dict(**options)
        d["function"] = self.function
        d["formula"] = self.formula
        d["expression"] = self.expression
        d["measure"] = self.measure

        return d


def create_attribute(obj, class_=None):
    """Makes sure that the `obj` is an ``Attribute`` instance. If `obj` is a
    string, then new instance is returned. If it is a dictionary, then the
    dictionary values are used for ``Attribute`` instance initialization."""

    class_ = class_ or Attribute

    if isinstance(obj, basestring):
        return class_(obj)
    elif isinstance(obj, dict):
        return class_(**obj)
    else:
        return obj


def attribute_list(attributes, class_=None):
    """Create a list of attributes from a list of strings or dictionaries.
    see :func:`cubes.coalesce_attribute` for more information."""

    if not attributes:
        return []

    result = [create_attribute(attr, class_) for attr in attributes]

    return result


def aggregate_list(aggregates):
    """Create a list of aggregates from aggregate metadata dictionaries (or
    list of names)"""
    return attribute_list(aggregates, class_=MeasureAggregate)


def measure_list(measures):
    """Create a list of measures from list of measure metadata (dictionaries
    or strings). The function tries to maintain cetrain level of backward
    compatibility with older models."""

    result = []

    for md in measures or []:
        if isinstance(md, Measure):
            result.append(md)
            continue

        if isinstance(md, basestring):
            md = {"name": md}
        else:
            md = dict(md)

        if "aggregations" in md and "aggregates" in md:
            raise ModelError("Both 'aggregations' and 'aggregates' specified "
                             "in a measure. Use only 'aggregates'")

        if "aggregations" in md:
            logger = get_logger()
            logger.warn("'aggregations' is depreciated, use 'aggregates'")
            md["aggregates"] = md.pop("aggregations")

        # Add default aggregation for 'sum' (backward compatibility)
        if not "aggregates" in md:
            md["aggregates"] = ["sum"]

        result.append(create_measure(md))

    return result


def create_cube(metadata):
    """Create a cube object from `metadata` dictionary. The cube has no
    dimensions attached after creation. You should link the dimensions to the
    cube according to the `Cube.linked_dimensions` property using
    `Cube.add_dimension()`"""

    if "name" not in metadata:
        raise ModelError("Cube has no name")

    metadata = dict(metadata)
    dimensions = metadata.pop("dimensions", [])

    if "measures" not in metadata and "aggregates" not in metadata:
        metadata["aggregates"] = [DEFAULT_RECORD_COUNT_AGGREGATE]

    # Prepare aggregate and measure lists, do implicit merging

    measures = measure_list(metadata.pop("measures", []))
    aggregates = metadata.pop("aggregates", [])
    aggregates = aggregate_list(aggregates)
    aggregate_dict = dict((a.name, a) for a in aggregates)
    measure_dict = dict((m.name, m) for m in measures)

    # TODO: change this to False in the future?
    if metadata.get("implicit_aggregates", True):
        implicit_aggregates = []
        for measure in measures:
            implicit_aggregates += measure.default_aggregates()

        for aggregate in implicit_aggregates:
            existing = aggregate_dict.get(aggregate.name)
            if existing:
                if existing.function != aggregate.function:
                    raise ModelError("Aggregate '%s' function mismatch. "
                                     "Implicit function %s, explicit function:"
                                     " %s." % (aggregate.name,
                                               aggregate.function,
                                               existing.function))
            else:
                aggregates.append(aggregate)
                aggregate_dict[aggregate.name] = aggregate

    # Assign implicit aggregate labels
    # TODO: make this configurable

    for aggregate in aggregates:
        try:
            measure = measure_dict[aggregate.measure]
        except KeyError:
            measure = aggregate_dict.get(aggregate.measure)

        if aggregate.label is None:
            aggregate.label = _measure_aggregate_label(aggregate, measure)

    return Cube(measures=measures, aggregates=aggregates,
                linked_dimensions=dimensions, **metadata)

def _measure_aggregate_label(aggregate, measure):
    function = aggregate.function
    template = IMPLICIT_AGGREGATE_LABELS.get(function, "{measure}")

    if aggregate.label is None and template:

        if measure:
            measure_label = measure.label or measure.name
        else:
            measure_label = aggregate.measure

        label = template.format(measure=measure_label)

    return label

def fix_dimension_metadata(metadata, create_levels=False):
    """Returns a dimension description as a dictionary. If provided as string,
    then it is going to be used as a name and as a single level. Defaults are
    applied to levels and hierarchies.
    """

    if isinstance(metadata, basestring):
        metadata = {"name":metadata, "levels": [metadata]}
    else:
        metadata = dict(metadata)

    if not "name" in metadata:
        raise ModelError("Dimension has no name")

    name = metadata["name"]

    # Fix levels
    levels = metadata.get("levels")
    if not levels and create_levels:
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
        levels = [fix_level_metadata(level) for level in levels]
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


def fix_level_metadata(metadata):
    """Returns a level description as a dictionary. If provided as string,
    then it is going to be used as level name and as its only attribute. If a
    dictionary is provided and has no attributes, then level will contain only
    attribute with the same name as the level name."""
    if isinstance(metadata, basestring):
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

    metadata["attributes"] = [fix_attribute_metadata(a) for a in attributes]

    # TODO: Backward compatibility – depreciate later
    if "cardinality" not in metadata:
        info = metadata.get("info", {})
        if "high_cardinality" in info:
            metadata["cardinality"] = "high"

    return metadata


def fix_attribute_metadata(metadata):
    """Fixes metadata of an attribute. If `metadata` is a string it will be
    converted into a dictionary with key `"name"` set to the string value."""
    if isinstance(metadata, basestring):
        metadata = {"name": metadata}

    return metadata


def create_dimension(metadata, templates=None, name=None):
    """Create a dimension from a `metadata` dictionary."""

    templates = templates or {}

    if "template" in metadata:
        template_name = metadata["template"]
        try:
            template = templates[template_name]
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
        cardinality = template.cardinality
        role = template.role
        category = template.category
    else:
        levels = []
        hierarchies = []
        default_hierarchy_name = None
        label = None
        description = None
        cardinality = None
        role = None
        category = None
        info = {}

    # Fix the metadata, but don't create default level if the template
    # provides levels.
    metadata = fix_dimension_metadata(metadata,
                                      create_levels=not bool(levels))

    name = metadata.get("name") or name
    if not name:
        raise ModelError("Dimension has no name, "
                         "neither explicit name provided")


    label = metadata.get("label") or label
    description = metadata.get("description") or description
    info = metadata.get("info") or info
    role = metadata.get("role") or role
    category = metadata.get("category") or category

    # Backward compatibility with an experimental feature
    cardinality = metadata.get("cardinality", cardinality)

    # Backward compatibility with an experimental feature:
    if not cardinality:
        info = metadata.get("info", {})
        if "high_cardinality" in info:
           cardinality = "high"

    # Levels
    # ------

    # We are guaranteed to have "levels" key from fix_dimension_metadata()

    if not levels:
        levels = [create_level(level) for level in metadata["levels"]]

    # Hierarchies
    # -----------
    if "hierarchies" in metadata:
        hierarchies = [Hierarchy(**md) for md in metadata["hierarchies"]]

    default_hierarchy_name = metadata.get("default_hierarchy_name",
                                          default_hierarchy_name)

    return Dimension(name=name,
                     levels=levels,
                     hierarchies=hierarchies,
                     default_hierarchy_name=default_hierarchy_name,
                     label=label,
                     description=description,
                     info=info,
                     cardinality=cardinality,
                     role=role,
                     category=category
                     )


def create_level(metadata, name=None, dimension=None):
    """Create a level object from metadata. `name` can override level name in
    the metadata."""

    metadata = dict(fix_level_metadata(metadata))

    try:
        name = name or metadata.pop("name")
    except KeyError:
        raise ModelError("No name specified in level metadata")

    attributes = attribute_list(metadata.pop("attributes"))

    # TODO: this should be depreciated
    for attribute in attributes:
        attribute.dimension = dimension

    return Level(name=name,
                 attributes=attributes,
                 dimension=dimension,
                 **metadata)


def localize_common(obj, trans):
    """Localize common attributes: label and description. `trans` should be a
    dictionary or a string. If it is just a string, then only `label` will be
    localized."""
    if isinstance(trans, basestring):
        obj.label = trans
    else:
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

    # FIXME: use some kind of class attribute to get list of localizable
    # attributes

    locale = {}
    if hasattr(obj, "label"):
        locale["label"] = obj.label

    if hasattr(obj, "description"):
        locale["description"] = obj.description

    return locale

