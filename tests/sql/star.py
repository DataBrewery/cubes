# -*- encoding: utf-8 -*-
#
# IMPORTANT: Analogous to the starschema.py, don't put any Cubes specific
# objects into this test case
#

from __future__ import absolute_import

import unittest
import sqlalchemy as sa
import sqlalchemy.sql as sql

from datetime import datetime
from cubes.sql.starschema import StarSchema, Mapping, StarSchemaError
from cubes.sql.starschema import NoSuchAttributeError
from cubes.sql.starschema import JoinKey, to_join_key, Join, to_join
from cubes.errors import ArgumentError

CONNECTION = "sqlite:///"

BASE_FACT = {
    "name": "test",
    "columns": ["date",      "category", "amount"],
    "types":   ["date",      "string",   "integer"],
    "data": [
               ["2014-01-01", "A",       1],
               ["2014-02-01", "B",       2],
               ["2014-03-01", "C",       4],
               ["2014-04-01", "D",       8],
            ]
}

DIM_CATEGORY = {
    "name": "dim_category",
    "columns": ["category", "label",      "size"],
    "types":   ["string",   "string",     "integer"],
    "data": [
               ["A",        "apple",      2],
               ["B",        "blueberry",  1],
               ["C",        "cantaloupe", 4],
               ["D",        "date",       1],
            ]
}

DIM_SIZE = {
    "name": "dim_size",
    "columns": ["size",    "label"],
    "types":   ["integer", "string"],
    "data": [
               [1,         "small"],
               [2,         "medium"],
               [4,         "large"],
            ]
}


def create_table(engine, md, desc):
    """Create a table according to description `desc`. The description
    contains keys:
    * `name` – table name
    * `columns` – list of column names
    * `types` – list of column types. If not specified, then `string` is
      assumed
    * `data` – list of lists representing table rows

    Returns a SQLAlchemy `Table` object with lodaded data.
    """

    TYPES = {
            "integer": sa.Integer,
            "string": sa.String,
            "date": sa.Date,
    }
    table = sa.Table(desc["name"], md,
                     sa.Column("id", sa.Integer, primary_key=True))

    types = desc.get("types")
    if not types:
        types = ["string"] * len(desc["columns"])

    col_types = dict(zip(desc["columns"], desc["types"]))
    for name, type_ in col_types.items():
        real_type = TYPES[type_]
        col = sa.Column(name, real_type)
        table.append_column(col)

    md.create_all()

    insert = table.insert()

    buffer = []
    for row in desc["data"]:
        record = {}
        for key, value in zip(desc["columns"], row):
            if col_types[key] == "date":
                value = datetime.strptime(value, "%Y-%m-%d")
            record[key] = value
        buffer.append(record)

    engine.execute(table.insert(buffer))

    return table

class SQLTestCase(unittest.TestCase):
    """Class with helper SQL assertion functions."""

    def assertColumnEqual(self, left, right):
        """Assert that the `left` and `right` columns have equal base columns
        depsite being labeled."""

        self.assertCountEqual(left.base_columns, right.base_columns)


class StarSchemaBasicsTestCase(SQLTestCase):
    def setUp(self):
        self.engine = sa.create_engine(CONNECTION)
        self.md = sa.MetaData(bind=self.engine)
        self.test_fact = create_table(self.engine, self.md, BASE_FACT)

    # TODO: do the same for a joined table and aliased joined table
    def test_physical_table(self):
        """Test denormalized table selection of few columns"""
        # Test passing fact by table object
        star = StarSchema("star", self.md, {}, self.test_fact)
        self.assertIs(star.physical_table("test"), self.test_fact)

        # Test passing fact by name
        star = StarSchema("star", self.md, {}, "test")
        self.assertIs(star.physical_table("test"), self.test_fact)

        # Test passing fact by name and in a list of tables

        star = StarSchema("star", self.md, {}, "test",
                         tables = {"test": self.test_fact})

        self.assertIs(star.physical_table("test"), self.test_fact)

        # Table does not exist
        with self.assertRaises(StarSchemaError):
            star.physical_table("imaginary")

    def test_collected_tables_fact_only(self):
        """Test single table references"""
        key = (None, "test")

        star = StarSchema("star", self.md, {}, self.test_fact)

        ref = star.table(key)
        self.assertIs(ref.table, self.test_fact)
        self.assertEqual(ref.name, "test")
        self.assertEqual(ref.alias, "test")
        self.assertEqual(ref.key, key)

        # Test passing fact by name
        star = StarSchema("star", self.md, {}, "test")

        ref = star.table(key)
        self.assertIs(ref.table, self.test_fact)

        # Test passing fact by name and in a list of tables
        star = StarSchema("star", self.md, {}, "test",
                         tables = {"test": self.test_fact})

        ref = star.table(key)
        self.assertIs(ref.table, self.test_fact)

        # Table does not exist
        with self.assertRaises(StarSchemaError):
            star.table((None, "imaginary"))

    def test_fact_columns(self):
        """Test fetching fact columns."""
        mappings = {
            "category": Mapping(None, "test", "category", None, None),
            "total":   Mapping(None, "test", "amount", None, None),
        }

        star = StarSchema("star", self.md, mappings, self.test_fact)

        column = star.column("category")
        self.assertEqual(column.name, "category")
        self.assertColumnEqual(column, self.test_fact.c.category)

        column = star.column("total")
        self.assertEqual(column.name, "total")
        self.assertColumnEqual(column, self.test_fact.c.amount)

        # Just satisfy caching coverage
        column = star.column("total")
        self.assertEqual(column.name, "total")

        # Test unknown column
        with self.assertRaises(NoSuchAttributeError):
            star.column("__unknown__")

    def test_unknown_column(self):
        """Test fetching fact columns."""
        mappings = {
            "category": Mapping(None, "test", "__unknown__", None, None),
        }

        star = StarSchema("star", self.md, mappings, self.test_fact)

        with self.assertRaises(StarSchemaError):
            column = star.column("category")

    def test_mapping_extract(self):
        """Test that mapping.extract works"""
        mappings = {
            "year": Mapping(None, "test", "date", "year", None),
        }

        star = StarSchema("star", self.md, mappings, self.test_fact)

        column = star.column("year")
        base = list(column.base_columns)[0]
        self.assertIsInstance(base, sa.sql.elements.Extract)
        self.assertEqual(base.field, "year")

        # TODO: test execute

    def test_relevant_joins_with_no_joins(self):
        mappings = {
            "category": Mapping(None, "test", "category", None, None),
            "amount":   Mapping(None, "test", "amount", None, None),
            "year":     Mapping(None, "test", "date", "year", None),
        }

        schema = StarSchema("star", self.md, mappings, self.test_fact)

        joins = schema.relevant_joins([])
        self.assertEqual(len(joins), 0)

        joins = schema.relevant_joins(["category", "amount"])
        self.assertEqual(len(joins), 0)

    def test_star_basic(self):
        """Test selection from the very basic star – no joins, just one
        table"""
        mappings = {
            "category": Mapping(None, "test", "category", None, None),
            "total":   Mapping(None, "test", "amount", None, None),
            "year":     Mapping(None, "test", "date", "year", None),
        }

        schema = StarSchema("star", self.md, mappings, self.test_fact)
        star = schema.star(["category", "total"])

        selection = [schema.column("category"), schema.column("total")]

        statement = sql.expression.select(selection,
                                          from_obj=star)
        result = self.engine.execute(statement)
        amounts = []

        for row in result:
            # We are testing proper column labeling
            amounts.append(row["total"])

        self.assertCountEqual(amounts, [1, 2, 4, 8])

    @unittest.skip("Missing test")
    def test_no_table_in_mapping(self):
        pass

class StarSchemaUtilitiesTestCase(unittest.TestCase):
    """Test independent utility functions and structures."""

    def test_to_join_key(self):
        """Test basic structure conversions."""

        self.assertEqual(JoinKey(None, None, None), to_join_key(None))

        key = to_join_key("col")
        self.assertEqual(JoinKey(None, None, "col"), key)

        key = to_join_key("table.col")
        self.assertEqual(JoinKey(None, "table", "col"), key)

        key = to_join_key("schema.table.col")
        self.assertEqual(JoinKey("schema", "table", "col"), key)

        key = to_join_key(["col"])
        self.assertEqual(JoinKey(None, None, "col"), key)

        key = to_join_key(["table", "col"])
        self.assertEqual(JoinKey(None, "table", "col"), key)

        key = to_join_key(["schema", "table", "col"])
        self.assertEqual(JoinKey("schema", "table", "col"), key)

        key = to_join_key({"column": "col"})
        self.assertEqual(JoinKey(None, None, "col"), key)

        key = to_join_key({"table":"table", "column": "col"})
        self.assertEqual(JoinKey(None, "table", "col"), key)

        key = to_join_key({"schema":"schema",
                           "table":"table",
                           "column": "col"})

        self.assertEqual(JoinKey("schema", "table", "col"), key)

        # Test exceptions
        #

        with self.assertRaises(ArgumentError):
            to_join_key([])

        with self.assertRaises(ArgumentError):
            to_join_key(["one", "two", "three", "four"])

        with self.assertRaises(ArgumentError):
            to_join_key("one.two.three.four")

    def test_to_join(self):
        join = ("left", "right")
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             None,
                                             None))

        join = ("left", "right", "alias")
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             None))

        join = ("left", "right", "alias", "match")
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             "match"))

        # Dict
        join = {"master": "left", "detail": "right"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             None,
                                             None))

        join = {"master": "left", "detail": "right", "alias": "alias"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             None))

        join = {"master": "left", "detail": "right", "method": "match"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             None,
                                             "match"))

        join = {"master": "left", "detail": "right", "alias": "alias",
                "method": "match"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             "match"))

        # Error
        with self.assertRaises(ArgumentError):
            to_join(["left", "right", "detail", "master", "something"])

        # Error
        with self.assertRaises(ArgumentError):
            to_join(["onlyone"])


class StarSchemaJoinsTestCase(SQLTestCase):
    def setUp(self):
        self.engine = sa.create_engine(CONNECTION)
        self.md = sa.MetaData(bind=self.engine)
        self.fact = create_table(self.engine, self.md, BASE_FACT)
        self.dim_category = create_table(self.engine, self.md, DIM_CATEGORY)
        self.dim_size = create_table(self.engine, self.md, DIM_SIZE)

    def test_join(self):
        """Test single join, two joins"""
        joins = [
            to_join(("test.category", "dim_category.category"))
        ]

        mappings = {
            "category":       Mapping(None, "test", "category", None, None),
            "amount":         Mapping(None, "test", "amount", None, None),
            "category_label": Mapping(None, "dim_category", "label", None, None),
            "size":           Mapping(None, "dim_category", "size", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        # Doe we have the joined table in the table list?
        table = schema.table((None, "dim_category"))
        self.assertEqual(table.table, self.dim_category)

        joins = schema.relevant_joins(["category"])
        self.assertEqual(len(joins), 0)

        joins = schema.relevant_joins(["amount"])
        self.assertEqual(len(joins), 0)

        joins = schema.relevant_joins(["category_label"])
        self.assertEqual(len(joins), 1)

        # Check columns
        self.assertColumnEqual(schema.column("category"),
                               self.fact.columns["category"])
        self.assertColumnEqual(schema.column("category_label"),
                               self.dim_category.columns["label"])
        self.assertColumnEqual(schema.column("size"),
                               self.dim_category.columns["size"])

    def test_join_alias(self):
        """Test single aliased join, test two joins on same table, one aliased
        """
        joins = [
            to_join(("test.category", "dim_category.category", "dim_fruit"))
        ]

        mappings = {
            "category":       Mapping(None, "test", "category", None, None),
            "amount":         Mapping(None, "test", "amount", None, None),
            "category_label": Mapping(None, "dim_fruit", "label", None, None),
            "size":           Mapping(None, "dim_fruit", "size", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        # Doe we have the joined table in the table list?
        # import pdb; pdb.set_trace()
        table = schema.table((None, "dim_fruit"))
        self.assertTrue(table.table.is_derived_from(self.dim_category))

        joins = schema.relevant_joins(["category_label"])
        self.assertEqual(len(joins), 1)

        # Check columns
        self.assertColumnEqual(schema.column("category"),
                               self.fact.columns["category"])
        self.assertColumnEqual(schema.column("category_label"),
                               self.dim_category.columns["label"])
        self.assertColumnEqual(schema.column("size"),
                               self.dim_category.columns["size"])

    def test_join_order(self):
        """Test that the order of joins does not matter"""

    def test_relevant_join(self):
        """Test that only tables containing required attributes are being
        joined"""

    def test_join_method_detail(self):
        """Test 'detail' join method"""

    def test_join_method_master(self):
        """Test 'detail' join master"""

    def test_unary(self):
        """Test that mapping.unary works"""

    def test_statement_table(self):
        """Test using a statement as a table"""

if __name__ == "__main__":
    unittest.main()
