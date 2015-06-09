# -*- encoding: utf-8 -*-
from __future__ import absolute_import

import sqlalchemy as sa
from sqlalchemy.sql.expression import ColumnElement

from unittest import TestCase, skip

from cubes.errors import ExpressionError
from cubes.sql.expressions import SQLExpressionCompiler, SQLExpressionContext
from .common import SQLTestCase

#

CONNECTION = "sqlite://"


class SQLExpressionTestCase(SQLTestCase):
    @classmethod
    def setUpClass(self):
        self.engine = sa.create_engine(CONNECTION)
        metadata = sa.MetaData(self.engine)
        self.table = sa.Table("data", metadata,
                        sa.Column("id", sa.Integer),
                        sa.Column("price", sa.Integer),
                        sa.Column("quantity", sa.Integer)
                    )
        metadata.create_all()

        insert = self.table.insert()
        data = [[1, 10, 1],
                [2, 20, 1],
                [3, 40, 2],
                [4, 80, 3]]

        for row in data:
            self.engine.execute(insert.values(row))

        self.bases = ["id", "price", "quantity"]
        self.columns = {attr:self.table.columns[attr]
                             for attr in self.bases}

    def setUp(self):
        self.context = SQLExpressionContext(self.columns)
        self.compiler = SQLExpressionCompiler()

    def column(self, name):
        return self.columns[name]

    def execute(self, *args, **kwargs):
        return self.engine.execute(*args, **kwargs)

    def assertExpressionEqual(self, left, right):
        """Asserts that the `left` and `right` statement expressions are equal
        by pulling out the data from the table and testing whether the
        returned sequences are equal."""

        stmt = sa.select([left.label("value")], from_obj=self.table)
        result = self.engine.execute(stmt)
        left_result = [row["value"] for row in result]


        stmt = sa.select([right.label("value")], from_obj=self.table)
        result = self.engine.execute(stmt)
        right_result = [row["value"] for row in result]

        self.assertCountEqual(left_result, right_result)


    def test_instance(self):
        self.assertIsInstance(self.compiler.compile("id", self.context),
                              ColumnElement)

        self.assertIsInstance(self.compiler.compile("1", self.context),
                              ColumnElement)

        self.assertIsInstance(self.compiler.compile("'text'", self.context),
                              ColumnElement)

        self.assertIsInstance(self.compiler.compile("1 + 1", self.context),
                              ColumnElement)

        self.assertIsInstance(self.compiler.compile("'text' + 1", self.context),
                              ColumnElement)

    def test_simple(self):
        column = self.compiler.compile("id", self.context)
        self.assertExpressionEqual(self.table.columns["id"], column)

    def test_with_constant(self):
        column = self.compiler.compile("price + 1", self.context)
        self.assertExpressionEqual(self.table.columns["price"] + 1,
                                   column)

        column = self.compiler.compile("price * 10 + 1", self.context)
        self.assertExpressionEqual((self.table.columns["price"] * 10) + 1,
                                   column)

    def test_multiple_columns(self):
        column = self.compiler.compile("price * quantity", self.context)
        self.assertExpressionEqual(self.table.columns["price"]
                                    * self.table.columns["quantity"],
                                   column)
    def test_unknown(self):
        with self.assertRaisesRegex(ExpressionError, "unknown"):
            column = self.compiler.compile("unknown", self.context)

    def test_incremental_context(self):
        with self.assertRaisesRegex(ExpressionError, "total"):
            column = self.compiler.compile("total", self.context)

        column = self.compiler.compile("price * quantity", self.context)
        self.context.add_column("total", column)

        column = self.compiler.compile("total", self.context)
        self.assertExpressionEqual(self.table.columns["price"]
                                    * self.table.columns["quantity"],
                                   column)

    def test_function(self):
        column = self.compiler.compile("min(price, 0)", self.context)
        self.assertExpressionEqual(sa.func.min(self.table.columns["price"], 0),
                                   column)
