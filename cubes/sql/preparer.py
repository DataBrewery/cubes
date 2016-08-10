# -*- encoding=utf -*-
"""
cubes.sql.preparer
~~~~~~~~~~~~~~~~~~

Star/snowflake schema query preparer

"""

import sqlalchemy.sql as sql
from sqlalchemy.sql.expression import and_

from ..metadata import object_dict
from ..errors import InternalError, ArgumentError, HierarchyError
from ..query import PointCut, SetCut, RangeCut
from ..query import SPLIT_DIMENSION_NAME

from .denormalizer import FACT_KEY_LABEL
from .expressions import compile_attributes


# TODO: Rename to QueryPreparer >>2.0
class QueryContext(object):
    """Context for execution of a query with given set of attributes and
    underlying star schema. The context is used for providing columns for
    attributes and generating conditions for cells. Context is reponsible for
    proper compilation of attribute expressions.

    Attributes:

    * `star` – a SQL expression object representing joined star for base
      attributes of the query. See :meth:`Denormalizer.denormalized_statement`
      for more information

    .. versionadded:: 1.1
    """

    def __init__(self, denormalizer, attributes, hierarchies=None,
                 parameters=None, safe_labels=None):
        """Creates a query context for `cube`.

        * `attributes` – list of all attributes that are relevant to the
           query. The attributes must be sorted by their dependency.
        * `hierarchies` is a dictionary of dimension hierarchies. Keys are
           tuples of names (`dimension`, `hierarchy`). The dictionary should
           contain default dimensions as (`dimension`, Null) tuples.
        * `safe_labels` – if `True` then safe column labels are created. Used
           for SQL dialects that don't support characters such as dot ``.`` in
           column labels.  See :meth:`QueryContext.column` for more
           information.

        `attributes` are objects that have attributes: `ref` – attribute
        reference, `is_base` – `True` when attribute does not depend on any
        other attribute and can be directly mapped to a column, `expression` –
        arithmetic expression, `function` – aggregate function (for
        aggregates only).

        Note: in the future the `hierarchies` dictionary might change just to
        a hierarchy name (a string), since hierarchies and dimensions will be
        both top-level objects.

        """

        # Note on why attributes have to be sorted: We don'd have enough
        # information here to get all the dependencies and we don't want this
        # object to depend on the complex Cube model object, just attributes.

        self.denormalizer = denormalizer

        self.attributes = object_dict(attributes, True)
        self.hierarchies = hierarchies
        self.safe_labels = safe_labels

        # Collect base attributes
        #
        base_names = [attr.ref for attr in attributes if attr.is_base]
        dependants = [attr for attr in attributes if not attr.is_base]

        # This is "the star" to be used by the owners of the context to select
        # from.
        #
        self.star = denormalizer.denormalized_statement(base_names)
        # TODO: determne from self.star

        # Collect all the columns
        #
        bases = {attr:self.denormalizer.column(attr) for attr in base_names}
        bases[FACT_KEY_LABEL] = self.denormalizer.fact_key_column

        self._columns = compile_attributes(bases, dependants, parameters,
                                           denormalizer.label)

        self.label_attributes = {}
        if self.safe_labels:
            # Re-label the columns using safe labels. It is up to the owner of
            # the context to determine which column is which attribute

            for i, item in enumerate(list(self._columns.items())):
                attr, column = item
                label = "a{}".format(i)
                self._columns[attr] = column.label(label)
                self.label_attributes[label] = attr
        else:
            for attr in attributes:
                attr = attr.ref
                column = self._columns[attr]
                self._columns[attr] = column.label(attr)
                # Identity mappign
                self.label_attributes[attr] = attr

    def column(self, ref):
        """Get a column expression for attribute with reference `ref`. Column
        has the same label as the attribute reference, unless `safe_labels` is
        provided to the query context. If `safe_labels` translation is
        provided, then the column has label according to the translation
        dictionary."""

        try:
            return self._columns[ref]
        except KeyError as e:
            # This should not happen under normal circumstances. If this
            # exception is raised, it very likely means that the owner of the
            # query contexts forgot to do something.
            raise InternalError("Missing column '{}'. Query context not "
                                "properly initialized or dependencies were "
                                "not correctly ordered?".format(ref))

    def get_labels(self, columns):
        """Returns real attribute labels for columns `columns`. It is highly
        recommended that the owner of the context uses this method before
        iterating over statement result."""

        if self.safe_labels:
            return [self.label_attributes.get(column.name, column.name)
                    for column in columns]
        else:
            return [col.name for col in columns]

    def get_columns(self, refs):
        """Get columns for attribute references `refs`.  """

        return [self._columns[ref] for ref in refs]

    def condition_for_cell(self, cell):
        """Returns a condition for cell `cell`. If cell is empty or cell is
        `None` then returns `None`."""

        if not cell:
            return None

        condition = and_(*self.conditions_for_cuts(cell.cuts))

        return condition

    def conditions_for_cuts(self, cuts):
        """Constructs conditions for all cuts in the `cell`. Returns a list of
        SQL conditional expressions.
        """

        conditions = []

        for cut in cuts:
            hierarchy = str(cut.hierarchy) if cut.hierarchy else None

            if isinstance(cut, PointCut):
                path = cut.path
                condition = self.condition_for_point(str(cut.dimension),
                                                     path,
                                                     hierarchy, cut.invert)

            elif isinstance(cut, SetCut):
                set_conds = []

                for path in cut.paths:
                    condition = self.condition_for_point(str(cut.dimension),
                                                         path,
                                                         str(cut.hierarchy),
                                                         invert=False)
                    set_conds.append(condition)

                condition = sql.expression.or_(*set_conds)

                if cut.invert:
                    condition = sql.expression.not_(condition)

            elif isinstance(cut, RangeCut):
                condition = self.range_condition(str(cut.dimension),
                                                 hierarchy,
                                                 cut.from_path,
                                                 cut.to_path, cut.invert)

            else:
                raise ArgumentError("Unknown cut type %s" % type(cut))

            conditions.append(condition)

        return conditions

    def condition_for_point(self, dim, path, hierarchy=None, invert=False):
        """Returns a `Condition` tuple (`attributes`, `conditions`,
        `group_by`) dimension `dim` point at `path`. It is a compound
        condition - one equality condition for each path element in form:
        ``level[i].key = path[i]``"""

        conditions = []

        levels = self.level_keys(dim, hierarchy, path)

        for level_key, value in zip(levels, path):

            # Prepare condition: dimension.level_key = path_value
            column = self.column(level_key)
            conditions.append(column == value)

        condition = sql.expression.and_(*conditions)

        if invert:
            condition = sql.expression.not_(condition)

        return condition

    def range_condition(self, dim, hierarchy, from_path, to_path,
                        invert=False):
        """Return a condition for a hierarchical range (`from_path`,
        `to_path`). Return value is a `Condition` tuple."""

        lower = self._boundary_condition(dim, hierarchy, from_path, 0)
        upper = self._boundary_condition(dim, hierarchy, to_path, 1)

        conditions = []
        if lower is not None:
            conditions.append(lower)
        if upper is not None:
            conditions.append(upper)

        condition = sql.expression.and_(*conditions)

        if invert:
            condition = sql.expression.not_(condition)

        return condition

    def _boundary_condition(self, dim, hierarchy, path, bound, first=True):
        """Return a `Condition` tuple for a boundary condition. If `bound` is
        1 then path is considered to be upper bound (operators < and <= are
        used), otherwise path is considered as lower bound (operators > and >=
        are used )"""
        # TODO: make this non-recursive

        if not path:
            return None

        last = self._boundary_condition(dim, hierarchy, path[:-1], bound,
                                        first=False)

        levels = self.level_keys(dim, hierarchy, path)

        conditions = []

        for level_key, value in zip(levels[:-1], path[:-1]):
            column = self.column(level_key)
            conditions.append(column == value)

        # Select required operator according to bound
        # 0 - lower bound
        # 1 - upper bound
        if bound == 1:
            # 1 - upper bound (that is <= and < operator)
            operator = sql.operators.le if first else sql.operators.lt
        else:
            # else - lower bound (that is >= and > operator)
            operator = sql.operators.ge if first else sql.operators.gt

        column = self.column(levels[-1])
        conditions.append(operator(column, path[-1]))
        condition = sql.expression.and_(*conditions)

        if last is not None:
            condition = sql.expression.or_(condition, last)

        return condition

    def level_keys(self, dimension, hierarchy, path):
        """Return list of key attributes of levels for `path` in `hierarchy`
        of `dimension`."""

        # Note: If something does not work here, make sure that hierarchies
        # contains "default hierarchy", that is (dimension, None) tuple.
        #
        try:
            levels = self.hierarchies[(str(dimension), hierarchy)]
        except KeyError as e:
            raise InternalError("Unknown hierarchy '{}'. Hierarchies are "
                                "not properly initialized (maybe missing "
                                "default?)".format(e))

        depth = 0 if not path else len(path)

        if depth > len(levels):
            levels_str = ", ".join(levels)
            raise HierarchyError("Path '{}' is longer than hierarchy. "
                                 "Levels: {}".format(path, levels))

        return levels[0:depth]

    def column_for_split(self, split_cell, label=None):
        """Create a column for a cell split from list of `cust`."""

        condition = self.condition_for_cell(split_cell)
        split_column = sql.expression.case([(condition, True)],
                                           else_=False)

        label = label or SPLIT_DIMENSION_NAME

        return split_column.label(label)

