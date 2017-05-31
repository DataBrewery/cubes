# -*- encoding: utf-8 -*-

from __future__ import absolute_import

import copy

from expressions import inspect_variables

from .base import ModelObject
from .. import compat
from ..errors import ModelError, ArgumentError, ExpressionError
from ..common import get_localizable_attributes

__all__ = [
    "AttributeBase",
    "Attribute",
    "Measure",
    "MeasureAggregate",

    "create_list_of",

    "collect_attributes",
    "depsort_attributes",
    "collect_dependencies",
    "expand_attribute_metadata",
]


def expand_attribute_metadata(metadata):
    """Fixes metadata of an attribute. If `metadata` is a string it will be
    converted into a dictionary with key `"name"` set to the string value."""
    if isinstance(metadata, compat.string_type):
        metadata = {"name": metadata}

    return metadata


class AttributeBase(ModelObject):
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
        * measure aggergate object preparation
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

