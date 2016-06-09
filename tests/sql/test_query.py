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
from cubes.sql.query import StarSchema, Column, SchemaError
from cubes.sql.query import NoSuchAttributeError
from cubes.sql.query import JoinKey, to_join_key, Join, to_join
from cubes.sql.query import QueryContext
from cubes.errors import ArgumentError, ModelError
from cubes.metadata import create_list_of, Attribute
from .common import create_table, SQLTestCase

CONNECTION = "sqlite://"

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
               ["E",        "e-fruit",    0],
            ]
}

DIM_SIZE = {
    "name": "dim_size",
    "columns": ["size",    "label"],
    "types":   ["integer", "string"],
    "data": [
               [0,         "invisible"],
               [1,         "small"],
               [2,         "medium"],
               [4,         "large"],
               [8,         "very large"],
            ]
}


class SchemaBasicsTestCase(SQLTestCase):
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
        with self.assertRaises(SchemaError):
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
        with self.assertRaises(SchemaError):
            star.table((None, "imaginary"))

    def test_fact_columns(self):
        """Test fetching fact columns."""
        mappings = {
            "category": Column(None, "test", "category", None, None),
            "total":   Column(None, "test", "amount", None, None),
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
            "category": Column(None, "test", "__unknown__", None, None),
        }

        star = StarSchema("star", self.md, mappings, self.test_fact)

        with self.assertRaises(SchemaError):
            column = star.column("category")

    def test_mapping_extract(self):
        """Test that mapping.extract works"""
        mappings = {
            "year": Column(None, "test", "date", "year", None),
        }

        star = StarSchema("star", self.md, mappings, self.test_fact)

        column = star.column("year")
        base = list(column.base_columns)[0]
        self.assertIsInstance(base, sa.sql.elements.Extract)
        self.assertEqual(base.field, "year")

        # TODO: test execute

    def test_required_tables_with_no_joins(self):
        mappings = {
            "category": Column(None, "test", "category", None, None),
            "amount":   Column(None, "test", "amount", None, None),
            "year":     Column(None, "test", "date", "year", None),
        }

        schema = StarSchema("star", self.md, mappings, self.test_fact)

        # Assumed fact
        tables = schema.required_tables([])
        self.assertEqual(len(tables), 1)
        self.assertIs(tables[0].table, schema.fact_table)

        tables = schema.required_tables(["category", "amount"])
        self.assertEqual(len(tables), 1)
        self.assertIs(tables[0].table, schema.fact_table)

    def test_star_basic(self):
        """Test selection from the very basic star – no joins, just one
        table"""
        mappings = {
            "category": Column(None, "test", "category", None, None),
            "total":   Column(None, "test", "amount", None, None),
            "year":     Column(None, "test", "date", "year", None),
        }

        schema = StarSchema("star", self.md, mappings, self.test_fact)
        star = schema.get_star(["category", "total"])

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

class SchemaUtilitiesTestCase(unittest.TestCase):
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


class SchemaJoinsTestCase(SQLTestCase):
    def setUp(self):
        self.engine = sa.create_engine(CONNECTION)
        self.md = sa.MetaData(bind=self.engine)
        self.fact = create_table(self.engine, self.md, BASE_FACT)
        self.dim_category = create_table(self.engine, self.md, DIM_CATEGORY)
        self.dim_size = create_table(self.engine, self.md, DIM_SIZE)

    def test_required_tables(self):
        """Test master-detail-detail snowflake chain joins"""
        joins = [
            to_join(("test.category", "dim_category.category")),
            to_join(("dim_category.size", "dim_size.size")),
        ]

        mappings = {
            "amount":         Column(None, "test", "amount", None, None),
            "category":       Column(None, "test", "category", None, None),
            "category_label": Column(None, "dim_category", "label", None, None),
            "size":           Column(None, "dim_category", "size", None, None),
            "size_label":     Column(None, "dim_size", "label", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        test_table = schema.table((None, "test"))
        category_table = schema.table((None, "dim_category"))
        size_table = schema.table((None, "dim_size"))

        all_tables = [test_table, category_table, size_table]

        tables = schema.required_tables(["size_label"])
        self.assertEqual(len(tables), 3)
        self.assertCountEqual(tables, all_tables)

        tables = schema.required_tables(["size_label", "category_label"])
        self.assertCountEqual(tables, all_tables)

        # Swap the attributes – it should return the same order
        tables = schema.required_tables(["category_label", "size_label"])
        self.assertCountEqual(tables, all_tables)

    def test_detail_twice(self):
        """Test exception when detail is specified twice (loop in graph)"""
        joins = [
            to_join(("test.category", "dim_category.category")),
            to_join(("dim_category.size", "dim_category.category")),
        ]

        with self.assertRaisesRegex(ModelError, "^Detail table.*joined twice"):
            StarSchema("star", self.md, {}, self.fact, joins=joins)

    def test_no_join_detail_table(self):
        joins = [
            to_join(("test.category", "category")),
        ]

        with self.assertRaisesRegex(ModelError, r"^No detail table"):
            StarSchema("star", self.md, {}, self.fact, joins=joins)

    def test_join(self):
        """Test single join, two joins"""
        joins = [
            to_join(("test.category", "dim_category.category"))
        ]
        mappings = {
            "category":       Column(None, "test", "category", None, None),
            "amount":         Column(None, "test", "amount", None, None),
            "category_label": Column(None, "dim_category", "label", None, None),
            "size":           Column(None, "dim_category", "size", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        # Doe we have the joined table in the table list?
        table = schema.table((None, "dim_category"))
        self.assertEqual(table.table, self.dim_category)

        tables = schema.required_tables(["category"])
        self.assertEqual(len(tables), 1)

        tables = schema.required_tables(["amount"])
        self.assertEqual(len(tables), 1)

        # Check columns
        self.assertColumnEqual(schema.column("category"),
                               self.fact.columns["category"])
        self.assertColumnEqual(schema.column("category_label"),
                               self.dim_category.columns["label"])
        self.assertColumnEqual(schema.column("size"),
                               self.dim_category.columns["size"])

    def test_compound_join_key(self):
        """Test compound (multi-column) join key"""
        joins = [
            to_join((
                {
                    "table": "test",
                    "column": ["category", "category"]
                },
                {
                    "table":"dim_category",
                    "column": ["category", "category"]
                }))
        ]

        mappings = {
            "category":       Column(None, "test", "category", None, None),
            "amount":         Column(None, "test", "amount", None, None),
            "category_label": Column(None, "dim_category", "label", None, None),
            "size":           Column(None, "dim_category", "size", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        # Doe we have the joined table in the table list?
        table = schema.table((None, "dim_category"))
        self.assertEqual(table.table, self.dim_category)

        tables = schema.required_tables(["category"])
        self.assertEqual(len(tables), 1)

        tables = schema.required_tables(["amount"])
        self.assertEqual(len(tables), 1)

        # Check columns
        self.assertColumnEqual(schema.column("category"),
                               self.fact.columns["category"])
        self.assertColumnEqual(schema.column("category_label"),
                               self.dim_category.columns["label"])
        self.assertColumnEqual(schema.column("size"),
                               self.dim_category.columns["size"])

        schema.get_star(["category_label"])

    def test_compound_join_different_length(self):
        """Test compound (multi-column) join key"""
        joins = [
            to_join((
                {
                    "table": "test",
                    "column": ["category", "category"]
                },
                {
                    "table":"dim_category",
                    "column": ["category"]
                }))
        ]

        mappings = {
            "category":       Column(None, "test", "category", None, None),
            "amount":         Column(None, "test", "amount", None, None),
            "category_label": Column(None, "dim_category", "label", None, None),
            "size":           Column(None, "dim_category", "size", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        # Doe we have the joined table in the table list?
        with self.assertRaisesRegex(ModelError, "different number"):
            schema.get_star(["category_label"])

    def test_join_alias(self):
        """Test single aliased join, test two joins on same table, one aliased
        """
        joins = [
            to_join(("test.category", "dim_category.category", "dim_fruit"))
        ]

        mappings = {
            "code":  Column(None, "test", "category", None, None),
            "fruit": Column(None, "dim_fruit", "label", None, None),
            "size":  Column(None, "dim_fruit", "size", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        # Doe we have the joined table in the table list?
        table = schema.table((None, "dim_fruit"))
        self.assertTrue(table.table.is_derived_from(self.dim_category))

        tables = schema.required_tables(["fruit"])
        self.assertEqual(len(tables), 2)

        # Check columns
        self.assertColumnEqual(schema.column("code"),
                               self.fact.columns["category"])
        self.assertColumnEqual(schema.column("fruit"),
                               self.dim_category.columns["label"])
        self.assertColumnEqual(schema.column("size"),
                               self.dim_category.columns["size"])

        # Check selectable statement
        star = schema.get_star(["code", "size"])
        selection = [schema.column("code"), schema.column("size")]
        select = sql.expression.select(selection,
                                       from_obj=star)
        result = self.engine.execute(select)
        sizes = [r["size"] for r in result]
        self.assertCountEqual(sizes, [2, 1, 4, 1])

    def test_fact_is_included(self):
        """Test whether the fact will be included in the star schema
        """
        joins = [
            to_join(("test.category", "dim_category.category", "dim_fruit"))
        ]

        mappings = {
            "code":  Column(None, "test", "category", None, None),
            "fruit": Column(None, "dim_fruit", "label", None, None),
            "size":  Column(None, "dim_fruit", "size", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        star = schema.get_star(["size"])
        selection = [schema.column("size")]
        select = sql.expression.select(selection,
                                       from_obj=star)
        result = self.engine.execute(select)
        sizes = [r["size"] for r in result]
        self.assertCountEqual(sizes, [2, 1, 4, 1])

    def test_snowflake_joins(self):
        """Test master-detail-detail snowflake chain joins"""
        joins = [
            to_join(("test.category", "dim_category.category")),
            to_join(("dim_category.size", "dim_size.size")),
        ]

        mappings = {
            "category":       Column(None, "test", "category", None, None),
            "category_label": Column(None, "dim_category", "label", None, None),
            "size":           Column(None, "dim_category", "size", None, None),
            "size_label":     Column(None, "dim_size", "label", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        # Construct the select for the very last attribute in the snowflake
        # arm
        # star = schema.star(["category_label", "size_label"])
        star = schema.get_star(["size_label", "category_label"])
        select = sql.expression.select([schema.column("size_label")],
                                       from_obj=star)
        result = self.engine.execute(select)
        sizes = [r["size_label"] for r in result]
        self.assertCountEqual(sizes, ["medium", "small", "large", "small"])

    def test_snowflake_aliased_joins(self):
        """Test master-detail-detail snowflake chain joins"""
        joins = [
            to_join(("test.category", "dim_category.category", "dim_fruit")),
            to_join(("dim_fruit.size", "dim_size.size"))
        ]

        mappings = {
            "category":       Column(None, "test", "category", None, None),
            "category_label": Column(None, "dim_fruit", "label", None, None),
            "size":           Column(None, "dim_fruit", "size", None, None),
            "size_label":     Column(None, "dim_size", "label", None, None),
        }

        schema = StarSchema("star", self.md, mappings, self.fact, joins=joins)

        table = schema.table((None, "dim_fruit"))
        self.assertTrue(table.table.is_derived_from(self.dim_category))

        table = schema.table((None, "dim_size"))
        self.assertTrue(table.table.is_derived_from(self.dim_size))

        # Check columns
        self.assertColumnEqual(schema.column("size_label"),
                               self.dim_size.columns["label"])

        # Construct the select for the very last attribute in the snowflake
        # arm
        star = schema.get_star(["size_label"])
        select = sql.expression.select([schema.column("size_label")],
                                       from_obj=star)
        result = self.engine.execute(select)
        sizes = [r["size_label"] for r in result]
        self.assertCountEqual(sizes, ["medium", "small", "large", "small"])

    def test_join_method_detail(self):
        """Test 'detail' join method"""

    def test_join_method_master(self):
        """Test 'detail' join master"""

    def test_unary(self):
        """Test that mapping.unary works"""

    def test_statement_table(self):
        """Test using a statement as a table"""
        joins = [
            to_join(("test.category", "dim_category.category"))
        ]

        mappings = {
            "code":  Column(None, "test", "category", None, None),
            "fruit": Column(None, "dim_category", "label", None, None),
            "size":  Column(None, "dim_category", "size", None, None),
        }

        fact_statement = sa.select(self.fact.columns, from_obj=self.fact,
                                   whereclause=self.fact.c.category == 'A')
        cat_statement = sa.select(self.dim_category.columns,
                                  from_obj=self.dim_category,
                                  whereclause=self.dim_category.c.category == 'A')

        tables = {
            "dim_category": cat_statement
        }

        with self.assertRaisesRegex(ArgumentError, "requires alias"):
            StarSchema("star", self.md, mappings,
                       fact=fact_statement,
                       tables=tables,
                       joins=joins)

        tables = {
            "dim_category": cat_statement.alias("dim_category")
        }

        schema = StarSchema("star", self.md, mappings,
                            fact=fact_statement.alias("test"),
                            tables=tables,
                            joins=joins)

        star = schema.get_star(["size"])
        selection = [schema.column("size")]
        select = sql.expression.select(selection,
                                       from_obj=star)
        result = self.engine.execute(select)
        sizes = [r["size"] for r in result]

        self.assertCountEqual(sizes, [2])

class QueryTestCase(SQLTestCase):
    def setUp(self):
        self.engine = sa.create_engine(CONNECTION)
        self.md = sa.MetaData(bind=self.engine)
        self.fact = create_table(self.engine, self.md, BASE_FACT)

        mappings = {
            "date":           Column(None, "test", "date", None, None),
            "amount":         Column(None, "test", "category", None, None),
            "category":       Column(None, "test", "amount", None, None),
        }
        self.deps = {
            "date": None,
            "amount": None,
            "category": None,
        }

        self.schema = StarSchema("star", self.md, mappings, self.fact)
        self.base_attributes = create_list_of(Attribute, mappings.keys())
        # self.base_attributes = list(mappings.keys())
        self.base_deps = {attr:[] for attr in self.base_attributes}


    def test_basic(self):
        context = QueryContext(self.schema, self.base_attributes,
                               self.base_deps)

if __name__ == "__main__":
    unittest.main()
