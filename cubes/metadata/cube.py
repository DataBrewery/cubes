# -*- encoding: utf-8 -*-
"""Cube logical model"""

from __future__ import absolute_import

from collections import OrderedDict, defaultdict

from ..common import assert_all_instances, get_localizable_attributes
# TODO: This should belong here
from ..query.statutils import aggregate_calculator_labels
from ..errors import ModelError, ArgumentError, NoSuchAttributeError
from ..errors import NoSuchDimensionError
from .base import ModelObject, object_dict
from .attributes import Attribute, Measure, MeasureAggregate
from .attributes import create_list_of, collect_dependencies
from .attributes import expand_attribute_metadata
from .dimension import Dimension

from .. import compat


__all__ = [
    "Cube",
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


class Cube(ModelObject):
    """Logical representation of a cube.

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


