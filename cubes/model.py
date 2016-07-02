# -*- encoding: utf-8 -*-
"""Logical model."""

from __future__ import absolute_import

import re
import copy

from collections import OrderedDict, defaultdict

from expressions import inspect_variables

from .common import IgnoringDictionary, to_label
from .common import assert_all_instances
from .common import get_localizable_attributes
from .errors import ModelError, ArgumentError, ExpressionError, HierarchyError
from .errors import NoSuchAttributeError, NoSuchDimensionError
from .errors import ModelInconsistencyError, TemplateRequired
from .statutils import aggregate_calculator_labels
from .metadata import expand_cube_metadata, expand_dimension_links
from .metadata import expand_dimension_metadata, expand_level_metadata
from . import compat


__all__ = [
    "ModelObject",
    "Cube",
    "Dimension",
    "Hierarchy",
    "Level",
    "AttributeBase",
    "Attribute",
    "Measure",
    "MeasureAggregate",

    "create_list_of",
    "object_dict",

    "collect_attributes",
    "depsort_attributes",
    "collect_dependencies",
    "string_to_dimension_level",
]


DEFAULT_FACT_COUNT_AGGREGATE = {
    "name": "fact_count",
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
    "time": ("year", "quarter", "month", "day", "hour", "minute", "second",
             "week", "weeknum", "dow",
             "isoyear", "isoweek", "isoweekday")
}


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


class Cube(ModelObject):

    localizable_attributes = ["label", "description"]
    localizable_lists = ["dimensions", "measures", "aggregates", "details"]

    @classmethod
    def from_metadata(cls, metadata):
        """Create a cube object from `metadata` dictionary. The cube has no
        dimensions attached after creation. You should link the dimensions to the
        cube according to the `Cube.dimension_links` property using
        `Cube._add_dimension()`"""

        if "name" not in metadata:
            raise ModelError("Cube metadata has no name")

        metadata = expand_cube_metadata(metadata)
        dimension_links = metadata.pop("dimensions", [])

        if "measures" not in metadata and "aggregates" not in metadata:
            metadata["aggregates"] = [DEFAULT_FACT_COUNT_AGGREGATE]

        # Prepare aggregate and measure lists, do implicit merging

        details = create_list_of(Attribute, metadata.pop("details", []))
        measures = create_list_of(Measure, metadata.pop("measures", []))

        # Inherit the nonadditive property in each measure
        nonadditive = metadata.pop("nonadditive", None)
        if nonadditive:
            for measure in measures:
                measure.nonadditive = nonadditive

        aggregates = metadata.pop("aggregates", [])
        aggregates = create_list_of(MeasureAggregate, aggregates)

        aggregate_dict = dict((a.name, a) for a in aggregates)
        measure_dict = dict((m.name, m) for m in measures)

        # TODO: Depreciate?
        if metadata.get("implicit_aggregates", False):
            implicit_aggregates = []
            for measure in measures:
                implicit_aggregates += measure.default_aggregates()

            for aggregate in implicit_aggregates:
                # an existing aggregate either has the same name,
                existing = aggregate_dict.get(aggregate.name)
                if existing:
                    if existing.function != aggregate.function:
                        raise ModelError("Aggregate '%s' function mismatch. "
                                         "Implicit function %s, explicit function:"
                                         " %s." % (aggregate.name,
                                                   aggregate.function,
                                                   existing.function))
                    continue
                # or the same function and measure
                existing = [agg for agg in aggregates
                            if agg.function == aggregate.function
                            and agg.measure == measure.name]

                if existing:
                    continue

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

            # Inherit nonadditive property from the measure
            if measure and aggregate.nonadditive is None:
                aggregate.nonadditive = measure.nonadditive

        return cls(measures=measures,
                   aggregates=aggregates,
                   dimension_links=dimension_links,
                   details=details,
                   **metadata)

    def __init__(self, name, dimensions=None, measures=None, aggregates=None,
                 label=None, details=None, mappings=None, joins=None,
                 fact=None, key=None, description=None, browser_options=None,
                 info=None, dimension_links=None, locale=None, category=None,
                 store=None, **options):

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
        * `dimension_links` – dimensions to be linked after the cube is
          created

        There are two ways how to assign dimensions to the cube: specify them
        during cube initialization in `dimensions` by providing a list of
        `Dimension` objects. Alternatively you can set `dimension_links`
        list with dimension names and the link the dimension using
        :meth:`cubes.Cube.link_dimension()`.

        Physical properties of the cube are described in the following
        attributes. They are used by the backends:

        * `mappings` - backend-specific logical to physical mapping
          dictionary. Keys and values of this dictionary are interpreted by
          the backend.
        * `joins` - backend-specific join specification (used for example in
          the SQL backend). It should be a list of dictionaries.
        * `fact` - fact table (collection, dataset, ...) name
        * `store` - name of data store where the cube belongs
        * `browser_options` - dictionary of other options used by the backend
          - refer to the backend documentation to see what options are used
          (for example SQL browser might look here for ``denormalized_view``
          in case of denormalized browsing)


        The dimension links are either dimension names or dictionaries
        specifying how the dimension will be linked to the cube. The keys of
        the link dictionary are:

        * `name` – name of the dimension to be linked
        * `hierarchies` – list of hierarchy names to be kept from the
          dimension
        * `nonadditive` – additivity of the linked dimension (overrides the
          dimension's value)
        * `cardinality` – cardinality of the linked dimension in the cube's
          context (overrides the dimension's value)
        * `default_hierarchy_name` – which hierarchy will be used as default
          in the linked dimension

        """

        super(Cube, self).__init__(name, label, description, info)

        if dimensions and dimension_links:
            raise ModelError("Both dimensions and dimension_links provided, "
                             "use only one.")

        self.locale = locale

        # backward compatibility
        self.category = category or self.info.get("category")

        # Physical properties
        self.mappings = mappings
        self.fact = fact
        self.joins = joins
        self.key = key
        self.browser_options = browser_options or {}
        self.browser = options.get("browser")

        self.dimension_links = OrderedDict()
        for link in expand_dimension_links(dimension_links or []):
            link = dict(link)
            name = link.pop("name")
            self.dimension_links[name] = link

        # Run-time properties
        # Sets in the Namespace.cube() when cube is created
        # Used by workspace internally to search for dimensions
        if isinstance(store, compat.string_type):
            self.store_name = store
            self.store = None
        else:
            self.store_name = options.get("store")
            self.store = store

        # TODO: make 'name' to be basename and ref to be full cube reference,
        # Be conistent!
        # Used by backends
        self.basename = self.name

        self._dimensions = OrderedDict()

        if dimensions:
            if not all([isinstance(dim, Dimension) for dim in dimensions]):
                raise ModelError("Dimensions for cube initialization should be "
                                 "a list of Dimension instances.")
            for dim in dimensions:
                self._add_dimension(dim)
        #
        # Prepare attributes
        # ------------------
        #
        # Measures

        measures = measures or []
        assert_all_instances(measures, Measure, "measure")
        self._measures = object_dict(measures,
                                     error_message="Duplicate measure {key} "
                                                   "in cube {cube}",
                                     error_dict={"cube": self.name})

        # Aggregates
        #
        aggregates = aggregates or []
        assert_all_instances(aggregates, MeasureAggregate, "aggregate")

        self._aggregates = object_dict(aggregates,
                                       error_message="Duplicate aggregate "
                                                     "{key} in cube {cube}",
                                       error_dict={"cube": self.name})

        # We don't need to access details by name
        details = details or []
        assert_all_instances(details, Attribute, "detail")
        self.details = details

    @property
    def measures(self):
        return list(self._measures.values())

    def measure(self, name):
        """Get measure object. If `obj` is a string, then measure with given
        name is returned, otherwise measure object is returned if it belongs
        to the cube. Returned object is of `Measure` type.

        Raises `NoSuchAttributeError` when there is no such measure or when
        there are multiple measures with the same name (which also means that
        the model is not valid).
        """

        name = str(name)
        try:
            return self._measures[name]
        except KeyError:
            raise NoSuchAttributeError("Cube '%s' has no measure '%s'" %
                                       (self.name, name))

    def get_measures(self, measures):
        """Get a list of measures as `Attribute` objects. If `measures` is
        `None` then all cube's measures are returned."""

        array = []

        for measure in measures or self.measures:
            array.append(self.measure(measure))

        return array

    @property
    def aggregates(self):
        return list(self._aggregates.values())

    def aggregate(self, name):
        """Get aggregate object. If `obj` is a string, then aggregate with
        given name is returned, otherwise aggregate object is returned if it
        belongs to the cube. Returned object is of `MeasureAggregate` type.

        Raises `NoSuchAttributeError` when there is no such aggregate or when
        there are multiple aggregates with the same name (which also means
        that the model is not valid).
        """
        name = str(name)
        try:
            return self._aggregates[name]
        except KeyError:
            raise NoSuchAttributeError("Cube '%s' has no measure aggregate "
                                       "'%s'" % (self.name, name))

    def get_aggregates(self, names=None):
        """Get a list of aggregates with `names`."""
        if not names:
            return self.aggregates

        return [self._aggregates[str(name)] for name in names]

    def aggregates_for_measure(self, name):
        """Returns aggregtates for measure with `name`. Only direct function
        aggregates are returned. If the measure is specified in an expression,
        the aggregate is not included in the returned list"""

        return [agg for agg in self.aggregates if agg.measure == name]

    @property
    def all_dimension_keys(self):
        """Returns all attributes that represent keys of dimensions and their
        levels..
        """

        attributes = []
        for dim in self.dimensions:
            attributes += dim.key_attributes

        return attributes

    @property
    def all_attributes(self):
        """All cube's attributes: attributes of dimensions, details, measures
        and aggregates. Use this method if you need to prepare structures for
        any kind of query. For attributes for more specific types of queries
        refer to :meth:`Cube.all_fact_attributes` and
        :meth:`Cube.all_aggregate_attributes`.

        .. versionchanged:: 1.1

            Returns all attributes, including aggregates. Original
            functionality is available as `all_fact_attributes()`

        """

        attributes = []
        for dim in self.dimensions:
            attributes += dim.attributes

        attributes += self.details
        attributes += self.measures
        attributes += self.aggregates

        return attributes

    @property
    def base_attributes(self):
        """Returns a list of attributes that are not derived from other
        attributes, do not depend on other cube attributes, variables or
        parameters. Any attribute that has an expression (regardless of it's
        contents, it might be a constant) is considered derived attribute.

        The list contains also aggregate attributes that are base – for
        example attributes that represent pre-aggregated column in a table.

        .. versionadded:: 1.1
        """

        return [attr for attr in self.all_attributes if attr.is_base]

    @property
    def all_fact_attributes(self):
        """All cube's attributes from the fact: attributes of dimensions,
        details and measures.

        .. versionadded:: 1.1
        """
        attributes = []
        for dim in self.dimensions:
            attributes += dim.attributes

        attributes += self.details

        attributes += self.measures

        return attributes

    @property
    def attribute_dependencies(self):
        """Dictionary of dependencies between attributes. Values are
        references of attributes that the key attribute depends on. For
        example for attribute `a` which has expression `b + c` the dictionary
        would be: `{"a": ["b", "c"]}`. The result dictionary includes all
        cubes' attributes and aggregates.

        .. versionadded:: 1.1
        """

        attributes = self.all_attributes + self.all_aggregate_attributes
        return {attr.ref:attr.dependencies for attr in attributes}

    @property
    def all_aggregate_attributes(self):
        """All cube's attributes for aggregation: attributes of dimensions and
        aggregates.  """

        attributes = []
        for dim in self.dimensions:
            attributes += dim.attributes

        attributes += self.aggregates

        return attributes

    def attribute(self, attribute):
        """Returns an attribute object (dimension attribute, measure or
        detail)."""

        # TODO: This should be a dictionary once the Cube object becomes
        # immutable

        name = str(attribute)

        for dim in self.dimensions:
            try:
                return dim.attribute(name, by_ref=True)
            except KeyError:
                continue

        for detail in self.details:
            if detail.name == name:
                return detail

        for measure in self.measures:
            if measure.name == name:
                return measure

        raise NoSuchAttributeError("Cube '%s' has no attribute '%s'"
                                   % (self.name, attribute))

    def get_attributes(self, attributes=None, aggregated=False):
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

        # TODO: this should be a dictionary created in __init__ once this
        # class becomes immutable

        if not attributes:
            if aggregated:
                return self.all_aggregate_attributes
            else:
                return self.all_fact_attributes

        everything = object_dict(self.all_attributes, True)

        names = (str(attr) for attr in attributes or [])

        result = []
        for name in names:
            try:
                attr = everything[name]
            except KeyError:
                raise NoSuchAttributeError("Unknown attribute '{}' in cube "
                                           "'{}'".format(name, self.name))
            result.append(attr)

        return result

    def collect_dependencies(self, attributes):
        """Collect all original and dependant cube attributes for
        `attributes`, sorted by their dependency: starting with attributes
        that don't depend on anything. For exapmle, if the `attributes` is [a,
        b] and a = c * 2, then the result list would be [b, c, a] or [c, b,
        a].

        This method is supposed to be used by backends that can handle
        attribute expressions.  It is safe to generate a mapping between
        logical references and their physical object representations from
        expressions in the order of items in the returned list.

        .. versionadded:: 1.1
        """

        depsorted = collect_dependencies(attributes, self.all_attributes)

        return self.get_attributes(depsorted)

    def link_dimension(self, dimension):
        """Links `dimension` object or a clone of it to the cube according to
        the specification of cube's dimension link. See
        :meth:`Dimension.clone` for more information about cloning a
        dimension."""

        link = self.dimension_links.get(dimension.name)

        if link:
            dimension = dimension.clone(**link)

        self._add_dimension(dimension)

    # TODO: this method should be used only during object initialization
    def _add_dimension(self, dimension):
        """Add dimension to cube. Replace dimension with same name. Raises
        `ModelInconsistencyError` when dimension with same name already exists
        in the receiver. """

        if not dimension:
            raise ArgumentError("Trying to add None dimension to cube '%s'."
                                % self.name)
        elif not isinstance(dimension, Dimension):
            raise ArgumentError("Dimension added to cube '%s' is not a "
                                "Dimension instance. It is '%s'"
                                % (self.name, type(dimension)))

        self._dimensions[dimension.name] = dimension

    @property
    def dimensions(self):
        return list(self._dimensions.values())

    def dimension(self, obj):
        """Get dimension object. If `obj` is a string, then dimension with
        given name is returned, otherwise dimension object is returned if it
        belongs to the cube.

        Raises `NoSuchDimensionError` when there is no such dimension.
        """

        # FIXME: raise better exception if dimension does not exist, but is in
        # the list of required dimensions

        if not obj:
            raise NoSuchDimensionError("Requested dimension should not be "
                                       "none (cube '{}')".format(self.name))

        name = str(obj)
        try:
            return self._dimensions[str(name)]
        except KeyError:
            raise NoSuchDimensionError("cube '{}' has no dimension '{}'"
                                       .format(self.name, name))

    @property
    def distilled_hierarchies(self):
        """Returns a dictionary of hierarchies. Keys are hierarchy references
        and values are hierarchy level key attribute references.

        .. warning::

            This method might change in the future. Consider experimental."""

        hierarchies = {}
        for dim in self.dimensions:
            for hier in dim.hierarchies:
                key = (dim.name, hier.name)
                levels = [hier_key.ref for hier_key in hier.keys()]

                hierarchies[key] = levels

                if dim.default_hierarchy_name == hier.name:
                    hierarchies[(dim.name, None)] = levels

        return hierarchies

    def to_dict(self, **options):
        """Convert to a dictionary. If `with_mappings` is ``True`` (which is
        default) then `joins`, `mappings`, `fact` and `options` are included.
        Should be set to ``False`` when returning a dictionary that will be
        provided in an user interface or through server API.
        """

        out = super(Cube, self).to_dict(**options)

        out["locale"] = self.locale
        out["category"] = self.category

        aggregates = [m.to_dict(**options) for m in self.aggregates]
        out["aggregates"] = aggregates

        measures = [m.to_dict(**options) for m in self.measures]
        out["measures"] = measures

        details = [a.to_dict(**options) for a in self.details]
        out["details"] = details

        if options.get("expand_dimensions"):
            limits = defaultdict(dict)

            # TODO: move this to metadata as strip_hierarchies()
            hierarchy_limits = options.get("hierarchy_limits")
            hierarchy_limits = hierarchy_limits or []

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

        if options.get("with_mappings"):
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
                results.append(('error', "Detail '%s' in cube '%s' is not "
                                         "instance of Attribute"
                                         % (detail, self.name)))
            if str(detail) in details:
                results.append(('error', "Duplicate detail '%s' in cube '%s'"\
                                            % (detail, self.name)))
            elif str(detail) in measures:
                results.append(('error', "Duplicate detail '%s' in cube '%s'"
                                         " - specified also as measure" \
                                         % (detail, self.name)))
            else:
                details.add(str(detail))

        # 2. check whether dimension attributes are unique

        return results

    def localize(self, trans):
        super(Cube, self).localized(trans)

        self.category = trans.get("category", self.category)

        attr_trans = trans.get("measures", {})
        for attrib in self.measures:
            attrib.localize(attr_trans.get(attrib.name, {}))

        attr_trans = trans.get("aggregates", {})
        for attrib in self.aggregates:
            attrib.localize(attr_trans.get(attrib.name, {}))

        attr_trans = trans.get("details", {})
        for attrib in self.details:
            attrib.localize(attr_trans.get(attrib.name, {}))

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

# Note: levels and hierarchies will be depreciated in the future versions.
# Levels will disappear and hierarchies will be top-level objects.

# TODO: Serves just as reminder for future direction. No real use yet.
class Conceptual(ModelObject):
    def levels(self):
        """Return list of levels of the conceptual object. Dimension returns
        just list of itself, hierarchy returns list of it's dimensions."""
        raise NotImplementedError("Subclasses sohuld implement levels")

    @property
    def is_flat(self):
        raise NotImplementedError("Subclasses should implement is_flat")


class Dimension(Conceptual):
    """
    Cube dimension.

    """

    localizable_attributes = ["label", "description"]
    localizable_lists = ["levels", "hierarchies"]

    @classmethod
    def from_metadata(cls, metadata, templates=None):
        """Create a dimension from a `metadata` dictionary.  Some rules:

        * ``levels`` might contain level names as strings – names of levels to
          inherit from the template
        * ``hierarchies`` might contain hierarchies as strings – names of
          hierarchies to inherit from the template
        * all levels that are not covered by hierarchies are not included in the
          final dimension

        """

        templates = templates or {}

        if "template" in metadata:
            template_name = metadata["template"]
            try:
                template = templates[template_name]
            except KeyError:
                raise TemplateRequired(template_name)

            levels = [copy.deepcopy(level) for level in template.levels]

            # Create copy of template's hierarchies, but reference newly
            # created copies of level objects
            hierarchies = []
            level_dict = dict((level.name, level) for level in levels)

            for hier in template._hierarchies.values():
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
            nonadditive = template.nonadditive
        else:
            template = None
            levels = []
            hierarchies = []
            default_hierarchy_name = None
            label = None
            description = None
            cardinality = None
            role = None
            category = None
            info = {}
            nonadditive = None

        # Fix the metadata, but don't create default level if the template
        # provides levels.
        metadata = expand_dimension_metadata(metadata,
                                             expand_levels=not bool(levels))

        name = metadata.get("name")

        label = metadata.get("label", label)
        description = metadata.get("description") or description
        info = metadata.get("info", info)
        role = metadata.get("role", role)
        category = metadata.get("category", category)
        nonadditive = metadata.get("nonadditive", nonadditive)

        # Backward compatibility with an experimental feature
        cardinality = metadata.get("cardinality", cardinality)

        # Backward compatibility with an experimental feature:
        if not cardinality:
            info = metadata.get("info", {})
            if "high_cardinality" in info:
               cardinality = "high"

        # Levels
        # ------

        # We are guaranteed to have "levels" key from expand_dimension_metadata()

        if "levels" in metadata:
            # Assure level inheritance
            levels = []
            for level_md in metadata["levels"]:
                if isinstance(level_md, compat.string_type):
                    if not template:
                        raise ModelError("Can not specify just a level name "
                                         "(%s) if there is no template for "
                                         "dimension %s" % (level_md, name))
                    level = template.level(level_md)
                else:
                    level = Level.from_metadata(level_md)
                    # raise NotImplementedError("Merging of levels is not yet supported")

                # Update the level's info dictionary
                if template:
                    try:
                        templevel = template.level(level.name)
                    except KeyError:
                        pass
                    else:
                        new_info = copy.deepcopy(templevel.info)
                        new_info.update(level.info)
                        level.info = new_info

                levels.append(level)

        # Hierarchies
        # -----------
        if "hierarchies" in metadata:
            hierarchies = _create_hierarchies(metadata["hierarchies"],
                                              levels,
                                              template)
        else:
            # Keep only hierarchies which include existing levels
            level_names = set([level.name for level in levels])
            keep = []
            for hier in hierarchies:
                if any(level.name not in level_names for level in hier.levels):
                    continue
                else:
                    keep.append(hier)
            hierarchies = keep


        default_hierarchy_name = metadata.get("default_hierarchy_name",
                                              default_hierarchy_name)

        if not hierarchies:
            # Create single default hierarchy
            hierarchies = [Hierarchy("default", levels=levels)]

        # Recollect levels – keep only those levels that are present in
        # hierarchies. Retain the original level order
        used_levels = set()
        for hier in hierarchies:
            used_levels |= set(level.name for level in hier.levels)

        levels = [level for level in levels if level.name in used_levels]

        return cls(name=name,
                   levels=levels,
                   hierarchies=hierarchies,
                   default_hierarchy_name=default_hierarchy_name,
                   label=label,
                   description=description,
                   info=info,
                   cardinality=cardinality,
                   role=role,
                   category=category,
                   nonadditive=nonadditive
                  )

    # TODO: new signature: __init__(self, name, *attributes, **kwargs):
    def __init__(self, name, levels=None, hierarchies=None,
                 default_hierarchy_name=None, label=None, description=None,
                 info=None, role=None, cardinality=None, category=None,
                 master=None, nonadditive=None, attributes=None, **desc):

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
        * `nonadditive` – kind of non-additivity of the dimension. Possible
          values: `None` (fully additive, default), ``time`` (non-additive for
          time dimensions) or ``all`` (non-additive for any other dimension)
        * `attributes` – attributes for dimension. Use either this or levels,
          not both.

        Dimension class is not meant to be mutable. All level attributes will
        have new dimension assigned.

        Note that the dimension will claim ownership of levels and their
        attributes. You should make sure that you pass a copy of levels if you
        are cloning another dimension.


        Note: The hierarchy will be owned by the dimension.
        """

        super(Dimension, self).__init__(name, label, description, info)

        self.role = role
        self.cardinality = cardinality
        self.category = category

        # Master dimension – dimension that this one was derived from, for
        # example by limiting hierarchies
        # TODO: not yet documented
        # TODO: probably replace the limit using limits in-dimension instead
        # of replacement of instance variables with limited content (?)
        self.master = master

        # Note: synchronize with Measure.__init__ if relevant/necessary
        if not nonadditive or nonadditive == "none":
            self.nonadditive = None
        elif nonadditive in ["all", "any"]:
            self.nonadditive = "all"
        elif nonadditive != "time":
            raise ModelError("Unknown non-additive diension type '%s'"
                             % nonadditive)

        self.nonadditive = nonadditive

        if not levels and not attributes:
            raise ModelError("No levels or attriutes specified for dimension %s" % name)
        elif levels and attributes:
            raise ModelError("Both levels and attributes specified")

        if attributes:
            # TODO: pass all level initialization arguments here
            level = Level(name, attributes=attributes)
            levels = [level]

        # Own the levels and their attributes
        self._levels = object_dict(levels)
        default_roles = _DEFAULT_LEVEL_ROLES.get(self.role)

        # Set default roles
        for level in self._levels.values():
            if default_roles and level.name in default_roles:
                level.role = level.name

        # Collect attributes
        self._attributes = OrderedDict()
        self._attributes_by_ref = OrderedDict()
        self._attributes = OrderedDict()
        for level in self.levels:
            for a in level.attributes:
                # Own the attribute
                if a.dimension is not None and a.dimension is not self:
                    raise ModelError("Dimension '%s' can not claim attribute "
                                     "'%s' because it is owned by another "
                                     "dimension '%s'."
                                     % (self.name, a.name, a.dimension.name))
                a.dimension = self
                self._attributes[a.name] = a
                self._attributes_by_ref[a.ref] = a

        # The hierarchies receive levels with already owned attributes
        if hierarchies:
            error_message = "Duplicate hierarchy '{key}' in cube '{cube}'"
            error_dict = {"cube": self.name}
            self._hierarchies = object_dict(hierarchies,
                                            error_message=error_message,
                                            error_dict=error_dict)
        else:
            default = Hierarchy("default", self.levels)
            self._hierarchies = object_dict([default])

        self._flat_hierarchy = None

        # Set default hierarchy specified by ``default_hierarchy_name``, if
        # the variable is not set then get a hierarchy with name *default* or
        # the first hierarchy in the hierarchy list.

        default_name = default_hierarchy_name or "default"
        hierarchy = self._hierarchies.get(default_name,
                                          list(self._hierarchies.values())[0])

        self._default_hierarchy = hierarchy
        self.default_hierarchy_name = hierarchy.name

    def __eq__(self, other):
        if other is None or type(other) != type(self):
            return False

        cond = self.name == other.name \
                and self.role == other.role \
                and self.label == other.label \
                and self.description == other.description \
                and self.cardinality == other.cardinality \
                and self.category == other.category \
                and self.default_hierarchy_name == other.default_hierarchy_name \
                and self._levels == other._levels \
                and self._hierarchies == other._hierarchies

        return cond

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def has_details(self):
        """Returns ``True`` when each level has only one attribute, usually
        key."""

        if self.master:
            return self.master.has_details

        return any([level.has_details for level in self._levels.values()])

    @property
    def levels(self):
        """Get list of all dimension levels. Order is not guaranteed, use a
        hierarchy to have known order."""
        return list(self._levels.values())

    @levels.setter
    def levels(self, levels):
        self._levels.clear()
        for level in levels:
            self._levels[level.name] = level

    @property
    def hierarchies(self):
        """Get list of dimension hierarchies."""
        return list(self._hierarchies.values())

    @hierarchies.setter
    def hierarchies(self, hierarchies):
        self._hierarchies.clear()
        for hier in hierarchies:
            self._hierarchies[hier.name] = hier

    @property
    def level_names(self):
        """Get list of level names. Order is not guaranteed, use a hierarchy
        to have known order."""
        return list(self._levels)

    def level(self, obj):
        """Get level by name or as Level object. This method is used for
        coalescing value"""
        if isinstance(obj, compat.string_type):
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
            return self._default_hierarchy
        if isinstance(obj, compat.string_type):
            if obj not in self._hierarchies:
                raise ModelError("No hierarchy %s in dimension %s" %
                                 (obj, self.name))
            return self._hierarchies[obj]
        elif isinstance(obj, Hierarchy):
            return obj
        else:
            raise ValueError("Unknown hierarchy object %s (should be a "
                             "string or Hierarchy instance)" % obj)

    def attribute(self, name, by_ref=False):
        """Get dimension attribute. `name` is an attribute name (default) or
        attribute reference if `by_ref` is `True`.`."""

        if by_ref:
            return self._attributes_by_ref[name]
        else:
            try:
                return self._attributes[name]
            except KeyError:
                raise NoSuchAttributeError("Unknown attribute '{}' "
                                           "in dimension '{}'"
                                           .format(name, self.name),
                                           name)


    @property
    def is_flat(self):
        """Is true if dimension has only one level"""
        if self.master:
            return self.master.is_flat

        return len(self.levels) == 1

    @property
    def key_attributes(self):
        """Return all dimension key attributes, regardless of hierarchy. Order
        is not guaranteed, use a hierarchy to have known order."""

        return [level.key for level in self._levels.values()]

    @property
    def attributes(self):
        """Return all dimension attributes regardless of hierarchy. Order is
        not guaranteed, use :meth:`cubes.Hierarchy.all_attributes` to get
        known order. Order of attributes within level is preserved."""

        return list(self._attributes.values())

    def clone(self, hierarchies=None, exclude_hierarchies=None,
              nonadditive=None, default_hierarchy_name=None, cardinality=None,
              alias=None, **extra):
        """Returns a clone of the receiver with some modifications. `master`
        of the clone is set to the receiver.

        * `hierarchies` – limit hierarchies only to those specified in
          `hierarchies`. If default hierarchy name is not in the new hierarchy
          list, then the first hierarchy from the list is used.
        * `exclude_hierarchies` – all hierarchies are preserved except the
          hierarchies in this list
        * `nonadditive` – non-additive value for the dimension
        * `alias` – name of the cloned dimension
        """

        if hierarchies == []:
            raise ModelInconsistencyError("Can not remove all hierarchies"
                                          "from a dimension (%s)."
                                          % self.name)

        if hierarchies:
            linked = []
            for name in hierarchies:
                linked.append(self.hierarchy(name))
        elif exclude_hierarchies:
            linked = []
            for hierarchy in self._hierarchies.values():
                if hierarchy.name not in exclude_hierarchies:
                    linked.append(hierarchy)
        else:
            linked = self._hierarchies.values()

        hierarchies = [copy.deepcopy(hier) for hier in linked]

        if not hierarchies:
            raise ModelError("No hierarchies to clone. %s")

        # Get relevant levels
        levels = []
        seen = set()

        # Get only levels used in the hierarchies
        for hier in hierarchies:
            for level in hier.levels:
                if level.name in seen:
                    continue

                levels.append(level)
                seen.add(level.name)

        # Dis-own the level attributes (we already have a copy)
        for level in levels:
            for attribute in level.attributes:
                attribute.dimension = None

        nonadditive = nonadditive or self.nonadditive
        cardinality = cardinality or self.cardinality

        # We are not checking whether the default hierarchy name provided is
        # valid here, as it was specified explicitly with user's knowledge and
        # we might fail later. However, we need to check the existing default
        # hierarchy name and replace it with first available hierarchy if it
        # is invalid.

        if not default_hierarchy_name:
            hier = self.default_hierarchy_name

            if any(hier.name == self.default_hierarchy_name for hier in hierarchies):
                default_hierarchy_name = self.default_hierarchy_name
            else:
                default_hierarchy_name = hierarchies[0].name

        # TODO: should we do deppcopy on info?
        name = alias or self.name

        return Dimension(name=name,
                         levels=levels,
                         hierarchies=hierarchies,
                         default_hierarchy_name=default_hierarchy_name,
                         label=self.label,
                         description=self.description,
                         info=self.info,
                         role=self.role,
                         cardinality=cardinality,
                         master=self,
                         nonadditive=nonadditive,
                         **extra)

    def to_dict(self, **options):
        """Return dictionary representation of the dimension"""

        out = super(Dimension, self).to_dict(**options)

        hierarchy_limits = options.get("hierarchy_limits")

        out["default_hierarchy_name"] = self.hierarchy().name

        out["role"] = self.role
        out["cardinality"] = self.cardinality
        out["category"] = self.category

        out["levels"] = [level.to_dict(**options) for level in self.levels]

        # Collect hierarchies and apply hierarchy depth restrictions
        hierarchies = []
        hierarchy_limits = hierarchy_limits or {}
        for name, hierarchy in self._hierarchies.items():
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

        if not self._hierarchies:
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
        else:  # if self._hierarchies
            if not self.default_hierarchy_name:
                if len(self._hierarchies) > 1 and \
                       "default" not in self._hierarchies:
                    results.append(('error',
                                    "No defaut hierarchy specified, there is "
                                    "more than one hierarchy in dimension "
                                    "'%s'" % self.name))

        if self.default_hierarchy_name \
                and not self._hierarchies.get(self.default_hierarchy_name):
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
                attr_name = attribute.ref
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
                                                          self._levels)

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        ldict = {}
        locale["levels"] = ldict

        for level in self.levels:
            ldict[level.name] = level.localizable_dictionary()

        hdict = {}
        locale["hierarchies"] = hdict

        for hier in self._hierarchies.values():
            hdict[hier.name] = hier.localizable_dictionary()

        return locale


def _create_hierarchies(metadata, levels, template):
    """Create dimension hierarchies from `metadata` (a list of dictionaries or
    strings) and possibly inherit from `template` dimension."""

    # Convert levels do an ordered dictionary for access by name
    levels = object_dict(levels)
    hierarchies = []

    # Construct hierarchies and assign actual level objects
    for md in metadata:
        if isinstance(md, compat.string_type):
            if not template:
                raise ModelError("Can not specify just a hierarchy name "
                                 "({}) if there is no template".format(md))
            hier = template.hierarchy(md)
        else:
            md = dict(md)
            level_names = md.pop("levels")
            hier_levels = [levels[level] for level in level_names]
            hier = Hierarchy(levels=hier_levels, **md)

        hierarchies.append(hier)

    return hierarchies


class Hierarchy(Conceptual):

    localizable_attributes = ["label", "description"]

    def __init__(self, name, levels, label=None, info=None, description=None):
        """Dimension hierarchy - specifies order of dimension levels.

        Attributes:

        * `name`: hierarchy name
        * `levels`: ordered list of levels or level names from `dimension`

        * `label`: human readable name
        * `description`: user description of the hierarchy
        * `info` - custom information dictionary, might be used to store
          application/front-end specific information

        Some collection operations might be used, such as ``level in hierarchy``
        or ``hierarchy[index]``. String value ``str(hierarchy)`` gives the
        hierarchy name.

        Note: The `levels` should have attributes already owned by a
        dimension.
        """

        super(Hierarchy, self).__init__(name, label, description, info)

        if not levels:
            raise ModelInconsistencyError("Hierarchy level list should "
                                          "not be empty (in %s)" % self.name)

        if any(isinstance(level, compat.string_type) for level in levels):
            raise ModelInconsistencyError("Levels should not be provided as "
                                          "strings to Hierarchy.")

        self._levels = object_dict(levels)

    def __deepcopy__(self, memo):
        return Hierarchy(self.name,
                         label=self.label,
                         description=self.description,
                         info=copy.deepcopy(self.info, memo),
                         levels=copy.deepcopy(self._levels.values(), memo))

    @property
    def levels(self):
        return list(self._levels.values())

    @levels.setter
    def levels(self, levels):
        self._levels.clear()
        for level in levels:
            self._levels[level.name] = level

    @property
    def level_names(self):
        return list(self._levels)

    def keys(self, depth=None):
        """Return names of keys for all levels in the hierarchy to `depth`. If
        `depth` is `None` then all levels are returned."""
        if depth is not None:
            levels = self.levels[0:depth]
        else:
            levels = self.levels

        return [level.key for level in levels]

    def __eq__(self, other):
        if not other or type(other) != type(self):
            return False

        return self.name == other.name and self.label == other.label \
                and self.levels == other.levels

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.name)

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
                                 (depth, self._levels, drilldown))

        return self.levels[0:depth + extend]

    def next_level(self, level):
        """Returns next level in hierarchy after `level`. If `level` is last
        level, returns ``None``. If `level` is ``None``, then the first level
        is returned."""

        if not level:
            return self.levels[0]

        index = list(self._levels).index(str(level))
        if index + 1 >= len(self.levels):
            return None
        else:
            return self.levels[index + 1]

    def previous_level(self, level):
        """Returns previous level in hierarchy after `level`. If `level` is
        first level or ``None``, returns ``None``"""

        if level is None:
            return None

        index = list(self._levels).index(str(level))
        if index == 0:
            return None
        else:
            return self.levels[index - 1]

    def level_index(self, level):
        """Get order index of level. Can be used for ordering and comparing
        levels within hierarchy."""
        try:
            return list(self._levels).index(str(level))
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
                raise HierarchyError("Can not roll-up: level '%s' – it is "
                                     "deeper than deepest element of path %s" %
                                     (str(level), path))
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

        out = super(Hierarchy, self).to_dict(**options)

        levels = [str(l) for l in self.levels]

        if depth:
            out["levels"] = levels[0:depth]
        else:
            out["levels"] = levels
        out["info"] = self.info

        return out

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        return locale


class Level(ModelObject):
    """Object representing a hierarchy level. Holds all level attributes.

    This object is immutable, except localization. You have to set up all
    attributes in the initialisation process.

    Attributes:

    * `name`: level name
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
    * `nonadditive` – kind of non-additivity of the level. Possible
      values: `None` (fully additive, default), ``time`` (non-additive for
      time dimensions) or ``all`` (non-additive for any other dimension)

    Cardinality values:

    * ``tiny`` – few values, each value can have it's representation on the
      screen, recommended: up to 5.
    * ``low`` – can be used in a list UI element, recommended 5 to 50 (if sorted)
    * ``medium`` – UI element is a search/text field, recommended for more than 50
      elements
    * ``high`` – backends might refuse to yield results without explicit
      pagination or cut through this level.

    Note: the `attributes` are going to be owned by the `dimension`.

    """

    localizable_attributes = ["label", "description"]
    localizable_lists = ["attributes"]

    @classmethod
    def from_metadata(cls, metadata, name=None, dimension=None):
        """Create a level object from metadata. `name` can override level name in
        the metadata."""

        metadata = dict(expand_level_metadata(metadata))

        try:
            name = name or metadata.pop("name")
        except KeyError:
            raise ModelError("No name specified in level metadata")

        attributes = []
        for attr_metadata in metadata.pop("attributes", []):
            attr = Attribute(dimension=dimension, **attr_metadata)
            attributes.append(attr)

        return cls(name=name, attributes=attributes, **metadata)

    def __init__(self, name, attributes, key=None, order_attribute=None,
                 order=None, label_attribute=None, label=None, info=None,
                 cardinality=None, role=None, nonadditive=None,
                 description=None):

        super(Level, self).__init__(name, label, description, info)

        self.cardinality = cardinality
        self.role = role

        if not attributes:
            raise ModelError("Attribute list should not be empty")

        self.attributes = attributes

        # Note: synchronize with Measure.__init__ if relevant/necessary
        if not nonadditive or nonadditive == "none":
            self.nonadditive = None
        elif nonadditive in ["all", "any"]:
            self.nonadditive = "all"
        elif nonadditive != "time":
            raise ModelError("Unknown non-additive diension type '%s'"
                             % nonadditive)
        self.nonadditive = nonadditive

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
                raise NoSuchAttributeError("Unknown order attribute {} in "
                                           "level {}"
                                           .format(order_attribute, self.name))
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
                or self.nonadditive != other.nonadditive \
                or self.attributes != other.attributes:
            return False

        return True

    def __hash__(self):
        return hash(self.name)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self.to_dict())

    def __deepcopy__(self, memo):
        if self.order_attribute:
            order_attribute = self.order_attribute.name
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
                     nonadditive=self.nonadditive,
                     role=self.role
                     )

    def to_dict(self, full_attribute_names=False, **options):
        """Convert to dictionary"""

        out = super(Level, self).to_dict(**options)

        out["role"] = self.role

        if full_attribute_names:
            out["key"] = self.key.ref
            out["label_attribute"] = self.label_attribute.ref
            out["order_attribute"] = self.order_attribute.ref
        else:
            out["key"] = self.key.name
            out["label_attribute"] = self.label_attribute.name
            out["order_attribute"] = self.order_attribute.name

        out["order"] = self.order
        out["cardinality"] = self.cardinality
        out["nonadditive"] = self.nonadditive

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

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        adict = {}
        locale["attributes"] = adict

        for attribute in self.attributes:
            adict[attribute.name] = attribute.localizable_dictionary()

        return locale


class AttributeBase(ModelObject):
    ASC = 'asc'
    DESC = 'desc'

    localizable_attributes = ["label", "description", "format"]

    @classmethod
    def from_metadata(cls, metadata):
        """Create an attribute from `metadata` which can be a dictionary or a
        string representing the attribute name.
        """

        if isinstance(metadata, compat.string_type):
            return cls(metadata)
        elif isinstance(metadata, cls):
            return copy.copy(metadata)
        elif isinstance(metadata, dict):
            if "name" not in metadata:
                raise ModelError("Model objects metadata require at least "
                                 "name to be present.")
            return cls(**metadata)

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, missing_value=None, expression=None,
                 **kwargs):
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
        * `expression` – arithmetic expression for computing this attribute
          from other existing attributes.

        String representation of the `AttributeBase` returns its `name`.

        `cubes.ArgumentError` is raised when unknown ordering type is
        specified.
        """
        super(AttributeBase, self).__init__(name, label, description, info)

        self.format = format
        self.missing_value = missing_value
        # TODO: temporarily preserved, this should be present only in
        # Attribute object, not all kinds of attributes
        self.dimension = None

        self.expression = expression
        self.ref = self.name

        if order:
            self.order = order.lower()
            if self.order.startswith("asc"):
                self.order = Attribute.ASC
            elif self.order.startswith("desc"):
                self.order = Attribute.DESC
            else:
                raise ArgumentError("Unknown ordering '%s' for attributes"
                                    " '%s'" % (order, self.ref))
        else:
            self.order = None

    def __str__(self):
        return self.ref

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
            and self.expression == other.expression \
            and self.missing_value == other.missing_value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.ref)

    def to_dict(self, **options):
        d = super(AttributeBase, self).to_dict(**options)

        d["format"] = self.format
        d["order"] = self.order
        d["missing_value"] = self.missing_value
        d["expression"] = self.expression

        d["ref"] = self.ref

        return d

    def localizable_dictionary(self):
        locale = {}
        locale.update(get_localizable_attributes(self))

        return locale

    def is_localizable(self):
        return False

    def localize(self, trans):
        """Localize the attribute, allow localization of the format."""
        super(AttributeBase, self).localized(trans)
        self.format = trans.get("format", self.format)

    @property
    def is_base(self):
        return not self.expression

    def localized_ref(self, locale):
        """Returns localized attribute reference for locale `locale`.
        """
        if locale:
            if not self.locales:
                raise ArgumentError("Attribute '{}' is not loalizable "
                                    "(localization {} requested)"
                                    .format(self.name, locale))
            elif locale not in self.locales:
                raise ArgumentError("Attribute '{}' has no localization {} "
                                    "(has: {})"
                                    .format(self.name, locale, self.locales))
            else:
                locale_suffix = "." + locale
        else:
            locale_suffix = ""

        return self.ref + locale_suffix

    @property
    def dependencies(self):
        """Set of attributes that the `attribute` depends on. If the
        `attribute` is an expresion, then returns the direct dependencies from
        the expression. If the attribute is an aggregate with an unary
        function operating on a measure, then the measure is considered as a
        dependency.  Attribute can't have both expression and measure
        specified, since you can have only expression or an function, not
        both.
        """
        if not self.expression:
            return set()

        return inspect_variables(self.expression)


class Attribute(AttributeBase):

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, dimension=None, locales=None,
                 missing_value=None, expression=None, **kwargs):
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

        Note: copied attributes are dis-owned from dimension. The new
        dimension has to be assigned after copying.
        """

        super(Attribute, self).__init__(name=name, label=label,
                                        description=description, order=order,
                                        info=info, format=format,
                                        missing_value=missing_value,
                                        expression=expression)
        self._dimension = None

        self.dimension = dimension
        self.locales = locales or []

    @property
    def dimension(self):
        return self._dimension

    @dimension.setter
    def dimension(self, dimension):
        if dimension:
            if dimension.is_flat and not dimension.has_details:
                self.ref = dimension.name
            else:
                self.ref = dimension.name + '.' + str(self.name)
        else:
            self.ref = str(self.name)
        self._dimension = dimension

    def __deepcopy__(self, memo):
        # Note: copied attribute is disowned
        return Attribute(self.name,
                         self.label,
                         dimension=None,
                         locales=copy.deepcopy(self.locales, memo),
                         order=copy.deepcopy(self.order, memo),
                         description=self.description,
                         info=copy.deepcopy(self.info, memo),
                         format=self.format,
                         missing_value=self.missing_value,
                         expression=self.expression)

    def __eq__(self, other):
        if not super(Attribute, self).__eq__(other):
            return False

        # TODO: we are not comparing dimension (owner) here
        return self.locales == other.locales

    def __hash__(self):
        return hash(self.ref)

    def to_dict(self, **options):
        # FIXME: Depreciated key "full_name" in favour of "ref"
        d = super(Attribute, self).to_dict(**options)

        d["locales"] = self.locales

        return d

    def is_localizable(self):
        return bool(self.locales)


class Measure(AttributeBase):
    """Cube measure attribute – a numerical attribute that can be
    aggregated."""

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, missing_value=None, aggregates=None,
                 formula=None, expression=None, nonadditive=None,
                 window_size=None, **kwargs):
        """Create a measure attribute. Properties in addition to the attribute
        base properties:

        * `formula` – name of a formula for the measure
        * `aggregates` – list of default (relevant) aggregate functions that
          can be applied to this measure attribute.
        * `nonadditive` – kind of non-additivity of the dimension. Possible
          values: `none` (fully additive, default), ``time`` (non-additive for
          time dimensions) or ``all`` (non-additive for any other dimension)

        Note that if the `formula` is specified, it should not refer to any
        other measure that refers to this one (no circular reference).

        The `aggregates` is an optional property and is used for:
        * measure aggregate object preparation
        * optional validation

        String representation of a `Measure` returns its full reference.
        """
        super(Measure, self).__init__(name=name, label=label,
                                      description=description, order=order,
                                      info=info, format=format,
                                      missing_value=None,
                                      expression=expression)

        self.formula = formula
        self.aggregates = aggregates
        self.window_size = window_size

        # Note: synchronize with Dimension.__init__ if relevant/necessary
        if not nonadditive or nonadditive == "none":
            self.nonadditive = None
        elif nonadditive in ["all", "any"]:
            self.nonadditive = "any"
        elif nonadditive == "time":
            self.nonadditive = "time"
        else:
            raise ModelError("Unknown non-additive measure type '%s'"
                             % nonadditive)

    def __deepcopy__(self, memo):
        return Measure(self.name, self.label,
                       order=copy.deepcopy(self.order, memo),
                       description=self.description,
                       info=copy.deepcopy(self.info, memo),
                       format=self.format,
                       missing_value=self.missing_value,
                       aggregates=self.aggregates,
                       expression=self.expression,
                       formula=self.formula,
                       nonadditive=self.nonadditive,
                       window_size=self.window_size)

    def __eq__(self, other):
        if not super(Measure, self).__eq__(other):
            return False

        return self.aggregates == other.aggregates \
                and self.formula == other.formula \
                and self.window_size == other.window_size

    def __hash__(self):
        return hash(self.ref)

    def to_dict(self, **options):
        d = super(Measure, self).to_dict(**options)
        d["formula"] = self.formula
        d["aggregates"] = self.aggregates
        d["window_size"] = self.window_size

        return d

    def default_aggregates(self):
        """Creates default measure aggregates from a list of receiver's
        measures. This is just a convenience function, correct models should
        contain explicit list of aggregates. If no aggregates are specified,
        then the only aggregate `sum` is assumed.
        """

        aggregates = []

        for agg in self.aggregates or ["sum"]:
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
                                         function=function,
                                         window_size=self.window_size)

            aggregate.label = _measure_aggregate_label(aggregate, self)
            aggregates.append(aggregate)

        return aggregates


class MeasureAggregate(AttributeBase):

    def __init__(self, name, label=None, description=None, order=None,
                 info=None, format=None, missing_value=None, measure=None,
                 function=None, formula=None, expression=None,
                 nonadditive=None, window_size=None, **kwargs):
        """Masure aggregate

        Attributes:

        * `function` – aggregation function for the measure
        * `formula` – name of a formula that contains the arithemtic
          expression (optional)
        * `measure` – measure name for this aggregate (optional)
        * `expression` – arithmetic expression (only if backend supported)
        * `nonadditive` – additive behavior for the aggregate (inherited from
          the measure in most of the times)
        """

        super(MeasureAggregate, self).__init__(name=name, label=label,
                                               description=description,
                                               order=order, info=info,
                                               format=format,
                                               missing_value=missing_value,
                                               expression=expression)

        self.function = function
        self.formula = formula
        self.measure = measure
        self.nonadditive = nonadditive
        self.window_size = window_size

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
                                expression=self.expression,
                                nonadditive=self.nonadditive,
                                window_size=self.window_size)

    def __eq__(self, other):
        if not super(MeasureAggregate, self).__eq__(other):
            return False

        return str(self.function) == str(other.function) \
            and self.measure == other.measure \
            and self.formula == other.formula \
            and self.nonadditive == other.nonadditive \
            and self.window_size == other.window_size

    def __hash__(self):
        return hash(self.ref)

    @property
    def is_base(self):
        return not self.expression and not self.function

    def to_dict(self, **options):
        d = super(MeasureAggregate, self).to_dict(**options)
        d["function"] = self.function
        d["formula"] = self.formula
        d["measure"] = self.measure
        d["nonadditive"] = self.nonadditive
        d["window_size"] = self.window_size

        return d

    @property
    def dependencies(self):
        """Set of attributes that the `attribute` depends on. If the
        `attribute` is an expresion, then returns the direct dependencies from
        the expression. If the attribute is an aggregate with an unary
        function operating on a measure, then the measure is considered as a
        dependency.  Attribute can't have both expression and measure
        specified, since you can have only expression or an function, not
        both.
        """
        if self.measure:
            if self.expression:
                raise ModelError("Aggregate '{}' has both measure and "
                                 "expression set".format(self.ref))
            return set([self.measure])

        if not self.expression:
            return set()

        return inspect_variables(self.expression)


def create_list_of(class_, objects):
    """Return a list of model objects of class `class_` from list of object
    metadata `objects`"""
    return [class_.from_metadata(obj) for obj in objects]


def _measure_aggregate_label(aggregate, measure):
    function = aggregate.function
    template = IMPLICIT_AGGREGATE_LABELS.get(function, "{measure}")

    if aggregate.label is None and template:

        if measure:
            measure_label = measure.label or measure.name
        else:
            if aggregate.measure:
                measure_label = aggregate.measure
            else:
                measure_label = aggregate.name

        label = template.format(measure=measure_label)

    return label


def collect_attributes(attributes, *containers):
    """Collect attributes from arguments. `containers` are objects with
    method `all_attributes` or might be `Nulls`. Returns a list of attributes.
    Note that the function does not check whether the attribute is an actual
    attribute object or a string."""
    # Method for decreasing noise/boilerplate

    collected = []

    if attributes:
        collected += attributes

    for container in containers:
        if container:
            collected += container.all_attributes

    return collected


def collect_dependencies(attributes, all_attributes):
    """Collect all original and dependant cube attributes for
    `attributes`, sorted by their dependency: starting with attributes
    that don't depend on anything. For exapmle, if the `attributes` is [a,
    b] and a = c * 2, then the result list would be [b, c, a] or [c, b,
    a].

    This method is supposed to be used by backends that can handle
    attribute expressions.  It is safe to generate a mapping between
    logical references and their physical object representations from
    expressions in the order of items in the returned list.

    Returns a list of sorted attribute references.
    """

    dependencies = {attr.ref:attr.dependencies for attr in all_attributes}
    # depsorted contains attribute names in order of dependencies starting
    # with base attributes (those that don't depend on anything, directly
    # represented by columns) and ending with derived attributes
    depsorted = depsort_attributes([attr.ref for attr in attributes],
                                   dependencies)

    return depsorted

def depsort_attributes(attributes, all_dependencies):
    """Returns a sorted list of attributes by their dependencies. `attributes`
    is a list of attribute names, `all_dependencies` is a dictionary where keys
    are attribute names and values are direct attribute dependencies (that is
    attributes in attribute's expression, for example). `all_dependencies`
    should contain all known attributes, variables and constants.

    Raises an exception when a circular dependecy is detected."""

    bases = set()

    # Gather only relevant dependencies
    required = set(attributes)

    # Collect base attributes and relevant dependencies
    seen = set()
    while required:
        attr = required.pop()
        seen.add(attr)

        try:
            attr_deps = all_dependencies[attr]
        except KeyError as e:
            raise ExpressionError("Unknown attribute '{}'".format(e))

        if not attr_deps:
            bases.add(attr)

        required |= set(attr_deps) - seen

    # Remaining dependencies to be processed (not base attributes)
    remaining = {attr:all_dependencies[attr] for attr in seen
                 if attr not in bases}

    sorted_deps = []

    while bases:
        base = bases.pop()
        sorted_deps.append(base)

        dependants = [attr for attr, deps in remaining.items()
                      if base in deps]

        for attr in dependants:
            # Remove the current dependency
            remaining[attr].remove(base)
            # If there are no more dependencies, consider the attribute to be
            # base
            if not remaining[attr]:
                bases.add(attr)
                del remaining[attr]

    if remaining:
        remaining_str = ", ".join(sorted(remaining))
        raise ExpressionError("Circular attribute reference (remaining: {})"
                              .format(remaining_str))

    return sorted_deps

def string_to_dimension_level(astring):
    """Converts `astring` into a dimension level tuple (`dimension`,
    `hierarchy`, `level`). The string should have a format:
    ``dimension@hierarchy:level``. Hierarchy and level are optional.

    Raises `ArgumentError` when `astring` does not match expected pattern.
    """

    if not astring:
        raise ArgumentError("Drilldown string should not be empty")

    ident = r"[\w\d_]"
    pattern = r"(?P<dim>%s+)(@(?P<hier>%s+))?(:(?P<level>%s+))?" % (ident,
                                                                    ident,
                                                                    ident)
    match = re.match(pattern, astring)

    if match:
        d = match.groupdict()
        return (d["dim"], d["hier"], d["level"])
    else:
        raise ArgumentError("String '%s' does not match drilldown level "
                            "pattern 'dimension@hierarchy:level'" % astring)


