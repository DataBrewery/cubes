# -*- encoding: utf-8 -*-

from __future__ import absolute_import

import sqlalchemy as sa
import sqlalchemy.sql as sql
from copy import copy

from cubes_lite import compat
from cubes_lite.errors import (
    ArgumentError, ModelError, NoSuchAttributeError, MissingObjectError,
)
from cubes_lite.model.utils import object_dict

from .functions import Function

__all__ = (
    'Mapper',
)


class NoSuchTableError(MissingObjectError):
    """Error related to the physical star schema."""
    pass


def _make_compound_key(table, key):
    """Returns a list of columns from `column_key` for `table` representing
    potentially a compound key. The `column_key` can be a name of a single
    column or list of column names."""

    if not isinstance(key, (list, tuple)):
        key = [key]

    return [table.columns[name] for name in key]


class Mapper(object):
    """Represents a star/snowflake table schema"""

    def __init__(self, cube, metadata):
        self.cube = cube
        self.metadata = metadata

        self.joins = [JoinObject.parse(join) for join in self.cube.joins]

        self._columns = {}  # keys: logical column names
        self._physical_tables = {}  # keys: tuples (schema, table physical name)

        self.root_table_object = TableObject.parse(self.cube.ref)
        self.root_table_object.table = self.construct_physical_table(
            name=self.root_table_object.name,
            schema=self.root_table_object.schema,
        )

        # keys: tuples (schema, table aliased name)
        self._table_objects = self._collect_tables()

    def __getitem__(self, key):
        return self._columns[key]

    def _collect_tables(self):
        """"
        Collect all the detail tables
        We don't need to collect the master tables as they are expected to
        be referenced as 'details'. The exception is the fact table that is
        provided explicitly for the snowflake schema.
        """

        table_objects = [self.root_table_object]

        for join in self.joins:
            table_name = join.detail.table

            if not table_name:
                raise ModelError(
                    'No detail table specified for a join "{}"'.format(join)
                )

            detail_table = self.construct_physical_table(
                name=table_name,
                schema=join.detail.schema,
            )

            if join.alias:
                detail_table = detail_table.alias(join.alias)

            obj = TableObject(
                table=detail_table,
                schema=join.detail.schema,
                name=table_name,
                alias=join.alias,
                join=join,
            )

            table_objects.append(obj)

        table_objects = object_dict(
            table_objects,
            key_func=lambda obj: (obj.schema, obj.alias or obj.name),
            error_message=(
                'Detail table "{key[1]}" joined twice in cube "{cube}".'
                'Unique join alias is required.'
            ),
            error_dict={'cube': self.cube.name},
        )

        # alias for fact table
        table_objects[(None, None)] = self.root_table_object

        return table_objects

    def get_table_object(self, key):
        """Return a table reference for `key` which has form of a
        tuple (`schema`, `table`).
        """

        if not key:
            raise ArgumentError('Table key should not be empty')

        try:
            return self._table_objects[key]
        except KeyError:
            schema = '"{}".'.format(key[0]) if key[0] else ''
            raise ModelError(
                'Unknown star table {}"{}". Missing join?'
                .format(schema, key[1])
            )

    def construct_physical_table(self, name, schema=None):
        """Return a physical table or table expression, regardless whether it
        exists or not in the star."""

        if '.' in name:
            if schema:
                raise ArgumentError('Ambiguous schema in "{}"'.format(name))

            schema, name = name.split('.', 1)

        key = (schema, name)
        table = self._physical_tables.get(key)
        if table is not None:
            return table

        try:
            table = sa.Table(
                name,
                self.metadata,
                autoload=True,
                schema=schema,
            )
        except sa.exc.NoSuchTableError:
            in_schema = ' in schema "{}"'.format(schema) if schema else ''
            msg = 'No such fact table "{}"{}'.format(name, in_schema)
            raise NoSuchTableError(msg)

        self._physical_tables[key] = table

        return table

    def get_column_by_attribute(self, attribute):
        """Return a column for `logical` reference. The returned column will
        have a label same as the column part of `logical`.
        """

        if isinstance(attribute, compat.string_type):
            attribute = self.cube.get_attributes([attribute])[0]

        logical = attribute.ref

        if logical in self._columns:
            return self._columns[logical]

        try:
            column_object = self.get_column_object_by_attribute(attribute)
        except KeyError:
            raise NoSuchAttributeError(logical)

        table_object = self.get_table_object(column_object.table_key)
        table = table_object.table

        try:
            column = table.columns[column_object.column]
        except KeyError:
            available = '", "'.join(str(c) for c in table.columns)
            raise ModelError(
                'Unknown column "{}" in table "{}" available columns: "{}"'
                .format(column_object.column, column_object.table, available)
            )

        if column_object.extract:
            column = sql.expression.extract(column_object.extract, column)

        if column_object.function:
            column = getattr(sql.expression.func, column_object.function)(column)

        column = column.label(column_object.column)

        self._columns[logical] = column
        return column

    def construct_column_for_attribute(self, attribute, columns):
        if isinstance(attribute, compat.string_type):
            attribute = self.cube.get_attributes([attribute])[0]

        names = [attribute.ref]

        try:
            column_object = self.get_column_object_by_attribute(attribute)
        except KeyError:
            raise NoSuchAttributeError(attribute)

        names.append(column_object.qualified_column)
        for name in names:
            try:
                column = columns[name]
                break
            except KeyError:
                continue
        else:
            raise ModelError('Unknown column "{}"'.format(name))

        if column_object.extract:
            column = sql.expression.extract(column_object.extract, column)

        if column_object.function:
            column = getattr(sql.expression.func, column_object.function)(column)

        label = attribute.ref if attribute.dimension.is_plain else attribute.base_name
        column = column.label(label)

        return column

    def get_column_object_by_attribute(self, attribute):
        """Returns implicit physical column reference for `attribute`, which
        should be an instance of :class:`cubes_lite.model.Attribute`. The
        returned reference has attributes `schema`, `table`, `column`,
        `extract`."""

        if not attribute.is_base:
            raise ModelError(
                'Attribute "{}" is dependant, it can not have a physical'
                'representation'
                .format(attribute.name),
            )

        physical = self.cube.mappings.get(attribute.ref)
        if physical:
            return ColumnObject.parse(physical)

        schema, table = self._ref_key_for_attribute(attribute)
        return ColumnObject.parse((schema, table, attribute.base_name))

    def _ref_key_for_attribute(self, attribute):
        """Return a tuple (schema, table) for attribute."""

        dimension = attribute.dimension

        if dimension.is_plain:
            table = self.cube.ref
        else:
            table = dimension.ref

        table = TableObject.parse(table)
        return (table.schema, table.name)

    def _required_tables(self, attributes, root_table_object=None):
        """Get all tables that are required to be joined to get `attributes`.
        `attributes` is a list of `Mapper` attributes (or objects with
        same kind of attributes).
        """

        root_table_object = root_table_object or self.root_table_object

        attributes = [attr for attr in attributes if attr.is_base]
        relevant_tables = set(
            self.get_table_object(self.get_column_object_by_attribute(a).table_key)
            for a in attributes
        )

        # now we have to resolve all dependencies
        required = {}
        while relevant_tables:
            table = relevant_tables.pop()
            required[table.key] = table

            if not table.join:
                continue

            master = table.join.master.table_key
            if master not in required:
                relevant_tables.add(self.get_table_object(master))

            detail = table.join.detail.table_key
            if table.join.alias:
                detail = (detail[0], table.join.alias)
            if detail not in required:
                relevant_tables.add(self.get_table_object(detail))

        # plain_dimensions = {a.dimension for a in attributes if a.dimension.is_plain}
        # if not plain_dimensions:
        #     required.pop(self.root_table_object.key, None)
        required.pop(self.root_table_object.key, None)
        required = {
            key: table
            for key, table in required.items()
            if (
                table.join.master.table is not None or
                table == root_table_object
            )
        }

        if root_table_object.key in required:
            masters = {root_table_object.key: root_table_object}
            sorted_tables = [root_table_object]
        else:
            details = [
                table for table in required.values()
                if table.join.method == 'detail'
            ]
            if details:
                first = details[0]
            else:
                first = required.values()[0]

            sorted_tables = [first]
            masters = {first.key: first}

        while required:
            details = [
                table for table in required.values()
                if table.join and table.join.master.table_key in masters
            ]

            if not details:
                break

            for detail in details:
                masters[detail.key] = detail
                sorted_tables.append(detail)

                del required[detail.key]

        if len(required) > 1:
            keys = [
                str(table)
                for table in required.values()
                if table.key != self.root_table_object.key
            ]

            raise ModelError(
                'Some tables are not joined: {}'
                .format(', '.join(keys))
            )

        return sorted_tables

    def get_joined_tables_for(self, attributes, root_table_object=None):
        """The main method for generating underlying star schema joins.
        Returns a denormalized JOIN expression that includes all relevant
        tables containing base `attributes` (attributes representing actual
        columns).
        """

        attributes = self.cube.get_attributes(attributes)
        table_objects = self._required_tables(attributes, root_table_object)

        return self.join_tables(table_objects)

    def join_tables(self, table_objects):
        # Dictionary of raw tables and their joined products
        # At the end this should contain only one item representing the whole
        # star.
        star_tables = {o.key: o.table for o in table_objects}

        # Here the `star` contains mapping table key -> table, which will be
        # gradually replaced by JOINs

        # Perform the joins
        # =================
        #
        # 1. find the column
        # 2. construct the condition
        # 3. use the appropriate SQL JOIN
        # 4. wrap the star with detail

        # first table does not need to be joined
        star = table_objects[0].table

        for table in table_objects[1:]:
            if not table.join:
                raise ModelError(
                    'Attempt to join the table "{}" without join spec'.format(table)
                )

            join = table.join

            # Get the physical table object (aliased) and already constructed
            # key (properly aliased)
            detail_table = table.table
            detail_key = table.key

            # The `table` here is a detail table to be joined. We need to get
            # the master table this table joins to:

            master = join.master
            master_key = master.table_key

            # We need plain tables to get columns for prepare the join
            # condition. We can't get it form `star`.

            # Master table.column
            master_table = self.get_table_object(master_key).table

            try:
                master_columns = _make_compound_key(master_table, master.column)
            except KeyError as e:
                raise ModelError(
                    'Unable to find master key column "{key}" '
                    'in table "{table}"'
                    .format(key=e, table=master_table)
                )

            # Detail table.column
            try:
                detail_columns = _make_compound_key(detail_table, join.detail.column)
            except KeyError as e:
                raise ModelError(
                    'Unable to find master key column "{key}" '
                    'in table "{table}"'
                        .format(key=e, table=detail_table)
                )

            if len(master_columns) != len(detail_columns):
                raise ModelError(
                    'Compound keys for master "{}" and detail '
                    '"{}" table have different number of columns'
                    .format(master_table, detail_table)
                )

            # the JOIN ON condition
            key_conditions = [
                left == right
                for left, right
                in zip(master_columns, detail_columns)
            ]
            onclause = sa.and_(*key_conditions)

            # Determine the join type based on the join method. If the method
            # is "detail" then we need to swap the order of the tables
            # (products), because SQLAlchemy provides inteface only for
            # left-outer join.
            left, right = (star, detail_table)

            if join.method is None or join.method == 'match':
                is_outer = False
            elif join.method == 'master':
                is_outer = True
            elif join.method == 'detail':
                # Swap the master and detail tables to perform RIGHT OUTER JOIN
                left, right = (right, left)
                is_outer = True
            else:
                raise ModelError('Unknown join method "{}"'.format(join.method))

            star = sql.expression.join(
                left, right,
                onclause=onclause,
                isouter=is_outer,
            )

            # Consume the detail
            if detail_key not in star_tables:
                raise ModelError(
                    'Detail table "{}" not in star. Missing join?'
                    .format(detail_table)
                )

            # The table is consumed by the join product, becomes the join
            # product itself.
            star_tables[detail_key] = star
            star_tables[master_key] = star

        return star

    def compile_aggregates(self, aggregates, base_columns=None, coalesce=True):
        aggregates = [self.cube.get_aggregate(a) for a in aggregates]

        if not base_columns:
            base_columns = self.cube.all_fact_attributes

        if not isinstance(base_columns, dict):
            base_columns = {c.name: c for c in base_columns}

        context = ColumnsContext(base_columns)

        # dependency resolution
        # maximum number of iterations: the worst case
        times = len(aggregates) ** 2

        sorted_dependants = []
        dependants = aggregates[:]
        for _ in range(times):
            if not dependants:
                break

            attr = dependants.pop(0)

            already_prepared = [dep.name for dep in sorted_dependants]
            if all(
                (related in context) or (related in already_prepared)
                for related in attr.depends_on
            ):
                # all dependencies already in context
                sorted_dependants.append(attr)
                continue

            dependants.append(attr)

        # construct all aggregates with its dependencies
        # in reverse-dependency order
        for attr in sorted_dependants:
            function_name = attr.function.lower()
            function = Function.get(function_name)
            column = function(attr, context, coalesce)

            context.add_column(attr.name, column)

        return [
            context.columns[a.name]
            for a in aggregates
        ]


class ColumnObject(object):
    """Physical column reference. `schema` is a database
    schema name, `table` is a table name containing the `column`.
    `extract` is an element to be extracted from complex data type such
    as date or JSON (in postgres). `function` is name of unary function to be
    applied on the `column`."""

    @classmethod
    def parse(cls, obj, default_table=None, default_schema=None):
        """Utility function that will create a `Column` reference object from an
           anonymous tuple, dictionary or a similar object. `obj` can also be a
           string in form ``schema.table.column`` where shcema or both schema
           and
           table can be ommited. `default_table` and `default_schema` are
           used when
           no table or schema is provided in `obj`.
           """

        if obj is None:
            raise ArgumentError('Mapping object can not be None')

        if isinstance(obj, compat.string_type):
            obj = obj.split('.')

        schema = None
        table = None
        column = None
        extract = None
        function = None

        if isinstance(obj, (tuple, list)):
            if len(obj) == 1:
                column = obj[0]
                table = None
                schema = None
            elif len(obj) == 2:
                table, column = obj
                schema = None
            elif len(obj) == 3:
                schema, table, column = obj
            else:
                raise ArgumentError(
                    'Join key can have 1 to 3 items (has "{}"): "{}"'
                        .format(len(obj), obj)
                )

        if hasattr(obj, 'get'):
            schema = obj.get('schema')
            table = obj.get('table')
            column = obj.get('column')
            extract = obj.get('extract')
            function = obj.get('function')

        if column is None:
            schema = obj.schema
            table = obj.table
            column = obj.column
            extract = obj.extract
            function = obj.function

        table = table or default_table
        schema = schema or default_schema

        if column is None:
            raise ArgumentError(
                'Cannot parse column representation: "{}"'
                .format(obj)
            )

        return cls(
            schema=schema, table=table, column=column,
            extract=extract, function=function,
        )

    def __init__(self, table, column, schema=None, extract=None, function=None):
        msg = 'Either `extract` or `function` can be used, not both'
        assert not all([extract, function]), msg

        self.table = table  # type: str
        self.column = column  # type: str
        self.schema = schema  # type: str
        self.extract = extract  # type: str
        self.function = function  # type: str

    def __str__(self):
        output = self.column

        if self.table:
            output = '{}.{}'.format(self.table, output)
        if self.schema:
            return '{}.{}'.format(self.schema, output)

        return output

    @property
    def table_key(self):
        return self.schema, self.table

    @property
    def qualified_column(self):
        if not self.table:
            return self.column
        return '{}.{}'.format(self.table, self.column)


class JoinObject(object):
    """Table join specification.
    `master` and `detail` are ColumnObjects.
    `method` - denotes which table members should be considered in the join:
        *master* - all master members (left outer join)
        *detail* - all detail members (right outer join)
        *match* - members must match (inner join).
    """

    @classmethod
    def parse(cls, obj):
        master = None
        detail = None
        alias = None
        method = None

        if isinstance(obj, (tuple, list)):
            if len(obj) < 2 or len(obj) > 4:
                raise ArgumentError(
                    'Join object can have 2 to 4 items (has "{}"): "{}"'
                    .format(len(obj), obj)
                )

            master = obj[0]
            detail = obj[1]

            if len(obj) == 3:
                alias = obj[2]
            if len(obj) == 4:
                alias = obj[2]
                method = obj[3]

        if hasattr(obj, 'get'):
            master = obj.get('master')
            detail = obj.get('detail')
            alias = obj.get('alias')
            method = obj.get('method')

        if detail is None:
            master = obj.master
            detail = obj.detail
            alias = obj.alias
            method = obj.method

        if detail is None:
            raise ArgumentError(
                'Cannot parse join representation: "{}"'
                    .format(obj)
            )

        master = ColumnObject.parse(master)
        detail = ColumnObject.parse(detail)

        return cls(master, detail, alias, method)

    def __init__(self, master, detail, alias=None, method=None):
        self.master = master  # type: ColumnObject
        self.detail = detail  # type: ColumnObject
        self.alias = alias  # type: str
        self.method = method  # type: str

    def __str__(self):
        return '{} -> {}'.format(self.master, self.detail)


class TableObject(object):
    """
        "schema",  # Database schema
        "name",  # Table name
        "alias",  # Optional table alias instead of name
        "key",  # Table key (for caching or referencing)
        "table",  # SQLAlchemy Table object, reflected
        "join"  # join which joins this table as a detail
    """

    @classmethod
    def parse(cls, obj):
        if not obj:
            raise ArgumentError('Mapping object can not be empty')

        if isinstance(obj, compat.string_type):
            obj = obj.split('.')

        schema = None
        name = None

        if isinstance(obj, (tuple, list)):
            if len(obj) == 1:
                name = obj[0]
                schema = None
            elif len(obj) == 2:
                schema, name = obj
            else:
                raise ArgumentError(
                    'Table name can have 1 to 2 items (has "{}"): "{}"'
                        .format(len(obj), obj)
                )

        if hasattr(obj, 'get'):
            schema = obj.get('schema')
            name = obj.get('name')

        if name is None:
            schema = obj.schema
            name = obj.name

        if name is None:
            raise ArgumentError(
                'Cannot parse table name representation: "{}"'
                .format(obj)
            )

        return cls(name=name, schema=schema)

    def __init__(self, name, alias=None, schema=None, table=None, join=None):
        self.name = name  # type: str
        self.alias = alias  # type: str
        self.schema = schema  # type: str
        self.table = table  # type: sa.Table or sa.Selectable
        self.join = join  # type: JoinObject

    def __str__(self):
        if self.schema:
            return '{}.{}'.format(self.schema, self.name)

        return self.name

    @property
    def key(self):
        return self.schema, self.alias or self.name

    def copy_with(self, table):
        result = copy(self)
        result.table = table
        return result


class ColumnsContext(object):
    """Context used for building a list of all columns to be used within a
    single SQL query."""

    def __init__(self, columns):
        """Creates a SQL expression context.
        * `bases` is a dictionary of base columns or column expressions
        * `parameters` is a flag where `True` means that the expression is
          expected to be an aggregate expression
        """

        if columns:
            self._columns = dict(columns)
        else:
            self._columns = {}

    @property
    def columns(self):
        return self._columns

    def resolve(self, variable):
        """Resolve `variable` – return either a column, variable from a
        dictionary or a SQL constant (in that order)."""

        if variable in self._columns:
            return self._columns[variable]

        raise ValueError(
            'Unknown variable "{}"'.format(variable)
        )

    def __getitem__(self, item):
        return self.resolve(item)

    def __contains__(self, item):
        return item in self._columns

    def add_column(self, name, column):
        self._columns[name] = column
