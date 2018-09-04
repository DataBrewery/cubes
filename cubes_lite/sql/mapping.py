# -*- encoding: utf-8 -*-

from __future__ import absolute_import

from collections import namedtuple

from .. import compat
from ..errors import ArgumentError, ModelError

__all__ = (
    'Mapper',
)


class Mapper(object):
    """A dictionary-like object that provides physical column references for
    cube attributes. Does implicit mapping of an attribute.
    """

    def __init__(self, cube):
        self.cube = cube

    def __getitem__(self, attribute):
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

        schema, table = self.table_for_attribute(attribute)
        return ColumnObject.parse((schema, table, attribute.base_name))

    def table_for_attribute(self, attribute):
        """Return a tuple (schema, table) for attribute."""

        dimension = attribute.dimension

        if dimension.is_flat:
            table = self.cube.ref
        else:
            table = dimension.ref

        if '.' not in table:
            schema = None
        else:
            schema = table.split('.', 1)[0]

        return (schema, table)

    def get_mapping(self):
        base_attrs = [attr for attr in self.cube.all_attributes if attr.is_base]
        return {attr.name: self[attr] for attr in base_attrs}


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

        return cls(schema, table, column, extract, function)

    def __init__(self, table, column, schema=None, extract=None, function=None):
        msg = 'Either `extract` or `function` can be used, not both'
        assert not all([extract, function]), msg

        self.table = table
        self.column = column
        self.schema = schema
        self.extract = extract
        self.function = function


class JoinObject(object):
    """Table join specification. `master` and `detail` are ColumnObjects.
    `method` denotes which table members should be considered in the join:
    *master* - all master members (left outer join), *detail* - all detail
    members (right outer join) and *match* - members must match (inner join).
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

            master = ColumnObject.parse(obj[0])
            detail = ColumnObject.parse(obj[1])

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
        self.master = master
        self.detail = detail
        self.alias = alias
        self.method = method


class TableObject(object):
    """
        "schema",  # Database schema
        "name",  # Table name
        "alias",  # Optional table alias instead of name
        "key",  # Table key (for caching or referencing)
        "table",  # SQLAlchemy Table object, reflected
        "join"  # join which joins this table as a detail
    """

    def __init__(self, name, key, alias=None, schema=None, table=None, join=None):
        self.name = name
        self.key = key
        self.alias = alias
        self.schema = schema
        self.table = table
        self.join = join
