# -*- encoding: utf-8 -*-
#
# IMPORTANT: Analogous to the starschema.py, don't put any Cubes specific
# objects into this test case
#

from __future__ import absolute_import

import unittest

from cubes.sql.starschema import StarSchema, Mapping, StarSchemaError
from cubes.sql.starschema import NoSuchAttributeError
import sqlalchemy as sa
from datetime import datetime

CONNECTION = "sqlite:///"

test_table = {
    "name": "test",
    "columns": ["date",      "category", "amount"],
    "types":   ["date",      "string",   "integer"],
    "data": [
               ["2014-01-01", "A",       "1"],
               ["2014-02-01", "B",       "2"],
               ["2014-03-01", "C",       "4"],
               ["2014-04-01", "D",       "8"],
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
        self.test_fact = create_table(self.engine, self.md, test_table)

    # TODO: do the same for a joined table and aliased joined table
    def test_physical_table(self):
        """Test denormalized table selection of few columns"""
        # Test passing fact by table object
        star = StarSchema("test_star", self.md, {}, self.test_fact)
        self.assertIs(star.physical_table("test"), self.test_fact)

        # Test passing fact by name
        star = StarSchema("test_star", self.md, {}, "test")
        self.assertIs(star.physical_table("test"), self.test_fact)

        # Test passing fact by name and in a list of tables

        star = StarSchema("test_star", self.md, {}, "test",
                         tables = {"test": self.test_fact})

        self.assertIs(star.physical_table("test"), self.test_fact)

        # Table does not exist
        with self.assertRaises(StarSchemaError):
            star.physical_table("imaginary")

    def test_collected_tables_fact_only(self):
        """Test single table references"""
        key = (None, "test")

        star = StarSchema("test_star", self.md, {}, self.test_fact)

        ref = star.table(key)
        self.assertIs(ref.table, self.test_fact)
        self.assertEqual(ref.name, "test")
        self.assertEqual(ref.alias, "test")
        self.assertEqual(ref.key, key)

        # Test passing fact by name
        star = StarSchema("test_star", self.md, {}, "test")

        ref = star.table(key)
        self.assertIs(ref.table, self.test_fact)

        # Test passing fact by name and in a list of tables
        star = StarSchema("test_star", self.md, {}, "test",
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

        star = StarSchema("test_star", self.md, mappings, self.test_fact)

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

        star = StarSchema("test_star", self.md, mappings, self.test_fact)

        with self.assertRaises(StarSchemaError):
            column = star.column("category")

    def test_mapping_extract(self):
        mappings = {
            "year": Mapping(None, "test", "date", "year", None),
        }

        star = StarSchema("test_star", self.md, mappings, self.test_fact)

        column = star.column("year")
        base = list(column.base_columns)[0]
        self.assertIsInstance(base, sa.sql.elements.Extract)
        self.assertEqual(base.field, "year")

        # TODO: test execute

    def test_join(self):
        """Test single join, two joins"""

    def test_join_alias(self):
        """Test single aliased join, test two joins on same table, one aliased
        """

    def test_join_order(self):
        """Test that the order of joins does not matter"""

    def test_relevant_join(self):
        """Test that only tables containing required attributes are being
        joined"""

    def test_join_method_detail(self):
        """Test 'detail' join method"""

    def test_join_method_master(self):
        """Test 'detail' join master"""

    def test_extract(self):
        """Test that mapping.extract works"""

    def test_unary(self):
        """Test that mapping.unary works"""

    def test_statement_table(self):
        """Test using a statement as a table"""

if __name__ == "__main__":
    unittest.main()
