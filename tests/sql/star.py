# -*- encoding: utf-8 -*-
#
# IMPORTANT: Analogous to the starschema.py, don't put any Cubes specific
# objects into this test case
#

from __future__ import absolute_import

import unittest

from cubes.sql.starschema import StarSchema, Mapping, StarSchemaError
import sqlalchemy as sa

CONNECTION = "sqlite:///"

test_table = {
    "name": "test",
    "columns": ["category", "amount"],
    "types":   ["string",   "integer"],
    "data":   [
                ["A",       "1"],
                ["B",       "2"],
                ["C",       "4"],
                ["D",       "8"],
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
            "datetime": sa.DateTime
    }
    table = sa.Table(desc["name"], md,
                     sa.Column("id", sa.Integer, primary_key=True))

    types = desc.get("types")
    if not types:
        types = ["string"] * len(desc["columns"])

    for name, type_ in zip(desc["columns"], desc["types"]):
        real_type = TYPES[type_]
        col = sa.Column(name, real_type)
        table.append_column(col)

    md.create_all()

    insert = table.insert()

    buffer = []
    for row in desc["data"]:
        record = dict(zip(desc["columns"], row))
        buffer.append(record)

    engine.execute(table.insert(buffer))

    return table


class StarSchemaBasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine(CONNECTION)
        self.md = sa.MetaData(bind=self.engine)
        self.test_fact = create_table(self.engine, self.md, test_table)

    def test_fact_basic(self):
        """Test denormalized table selection of few columns"""
        mappings = {
            "category": Mapping(None, "test", "category", None, None),
            "amount":   Mapping(None, "test", "amount", None, None),
        }

        key = (None, "test")

        # Test passing fact by table object

        star = StarSchema("test_star", self.md, mappings, self.test_fact)

        self.assertIn(key, star.tables)
        table = star.table(key)
        self.assertIs(table, self.test_fact)

        # Test passing fact by name

        star = StarSchema("test_star", self.md, mappings, "test")

        self.assertIn(key, star.tables)
        table = star.table(key)
        self.assertIs(table, self.test_fact)

        # Test passing fact by name and in a list of tables

        star = StarSchema("test_star", self.md, mappings, "test",
                         tables = {"test": self.test_fact})

        self.assertIn(key, star.tables)
        table = star.table(key)
        self.assertIs(table, self.test_fact)

        # Table does not exist
        with self.assertRaises(StarSchemaError):
            table = star.table((None, "imaginary"))


    def test_non_existent_table(self):
        pass

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
