# -*- coding: utf-8 -*-
"""Database for testing the SQL browser – schema and data.


Contains:

* star schema
* snowflake schema
* dimension with three levels of hierarchy
* date dimension
* date field (for 'extract')
* measure fields that can be used for expressions
* dimension with more than one attribute
* folows a naming convention (ft_, dim_, _key, ...)

"""
#
# See: https://github.com/DataBrewery/cubes/issues/255
#

from __future__ import print_function

import sqlalchemy as sa
import os
import json

from collections import OrderedDict
from datetime import datetime, date, timedelta
from cubes import ModelProvider


SRC_SALES = {
    "name": "src_sales",
    "columns": (
        ("id",       "id"),
        ("date",     "date"),
        ("location", "string"),
        ("item",     "string"),
        ("quantity", "integer"),
        ("price",    "integer"),
        ("discount", "integer"),
    ),
    #
    # Data requirements for SQL browser test:
    #  * only one entry for date 2015-01-01
    #
    "data": [
        ( 1, "2015-01-01", "here",   "apricot", 1,  3,  0),
        ( 2, "2015-01-02", "here",   "plum",    2,  1,  0),
        ( 3, "2015-01-03", "here",   "goat",    1,  1,  0),
        ( 4, "2015-01-04", "here",   "apricot", 2,  6,  0),
        ( 5, "2015-01-05", "there",  "shirt",   2, 20, 10),
        ( 6, "2015-02-01", "there",  "jacket",  1, 50, 10),
        ( 7, "2015-02-01", "there",  "apricot", 2,  6,  0),
        ( 8, "2015-03-01", "there",  "apricot", 2,  6, 50),
        ( 9, "2015-04-01", "unknown","apricot", 2,  6, 50),
    ]
}

FACT_SALES = {
    "name": "fact_sales",
    "columns": (
        ("id",            "id"),
        ("date_key",      "integer"),
        ("item_key",      "integer"),
        ("category_key",  "integer"),
        ("department_key","integer"),
        ("quantity",      "integer"),
        ("price",         "integer"),
        ("discount",      "integer"),
    )
}

FACT_SALES_DENORM = {
    "name": "fact_sales_denorm",
    "columns": (
        ("id",              "id"),
        ("date_key",        "integer"),
        ("date",            "date"),
        ("item_key",        "integer"),
        ("item_name",       "string"),
        ("item_unit_price", "integer"),
        ("category_key",    "integer"),
        ("category_name",   "string"),
        ("department_key",  "integer"),
        ("department_name", "string"),
        ("quantity",        "integer"),
        ("price",           "integer"),
        ("discount",        "integer"),
    )
}

DIM_ITEMS = {
    "name": "dim_item",
    "columns": [
        ("item_key",       "id"),
        ("name",           "string"),
        ("category_key",   "integer"),
        ("category",       "string"),
        ("unit_price",     "integer")
    ],
    "data": [
        ( 1, "apricot",   1, "produce",  3),
        ( 2, "plum",      1, "produce",  2),
        ( 3, "carrot",    1, "produce",  1),
        ( 4, "celery",    1, "produce",  2),
        ( 5, "milk",      2, "dairy",    2),
        ( 6, "cheese",    2, "dairy",    5),
        ( 7, "bread",     3, "bakery",   3),
        ( 8, "rolls",     3, "bakery",   1),
        ( 9, "chicken",   4, "meat",     4),
        (10, "beef",      4, "meat",     8),
        (11, "goat",      4, "meat",     7),

        (12, "soap",      5, "hygiene",  1),
        (13, "lotion",    5, "hygiene",  5),
        (14, "shirt",     6, "formal",  20),
        (15, "pants",     6, "formal",  30),
        (16, "jacket",    7, "casual",  50),
        (17, "shorts",    7, "casual",  25),
    ]
}


DIM_CATEGORIES = {
    "name": "dim_category",
    "columns": [
        ("category_key",   "id"),
        ("name",           "string"),
        ("department_key", "integer"),
        ("department",     "string")
    ],
    "data": [
        (1, "produce", 1, "grocery"),
        (2, "dairy",   1, "grocery"),
        (3, "bakery",  1, "grocery"),
        (4, "meat",    1, "grocery"),
        (5, "hygiene", 2, "body"),
        (6, "formal",  3, "fashion"),
        (7, "casual",  3, "fashion"),
    ]
}

DIM_DEPARTMENTS = {
    "name": "dim_department",
    "columns": [
        ("department_key",   "id"),
        ("name",             "string"),
        ("manager",          "string"),
    ],
    "data": [
        (1, "grocery", "Michael"),
        (2, "body",    "Marek"),
        (3, "fashion", "Sebastian"),
    ]
}


DEFAULT_DB_URL = "sqlite://"


month_to_quarter = lambda month: ((month - 1) // 3) + 1


class TinyDemoDataWarehouse(object):
    def __init__(self, url=None, schema=None, recreate=False):
        if "CUBES_TEST_DB" in os.environ:
            url = os.environ["CUBES_TEST_DB"]
        else:
            url = url or DEFAULT_DB_URL

        self.engine = sa.create_engine(url)

        if recreate:
            self.engine.execute("DROP SCHEMA IF EXISTS {} CASCADE".format(schema))
            self.engine.execute("CREATE SCHEMA {}".format(schema))

        self.md = sa.MetaData(self.engine, schema=schema)
        self.schema = schema

    def create_table(self, desc, name=None):
        """Create a table according to description `desc`. The description
        contains keys:
        * `name` – table name
        * `columns` – list of column names
        * `types` – list of column types. If not specified, then `string` is
          assumed
        * `data` – list of lists representing table rows.

        Returns a SQLAlchemy `Table` object with lodaded data.
        """

        TYPES = {
                "integer": sa.Integer,
                "string": sa.String,
                "date": sa.DateTime,
                "id": sa.Integer,
        }

        name = name or desc["name"]

        table = sa.Table(desc["name"], self.md)
        col_types = {}

        columns = desc["columns"]

        for col_info in columns:
            name, type_ = col_info[:2]
            col_types[name] = type_

            real_type = TYPES[type_]

            if type_ == 'id':
                col = sa.Column(name, real_type, primary_key=True)
            else:
                col = sa.Column(name, real_type)

            table.append_column(col)

        self.md.create_all()

        insert = table.insert()

        names = [c[0] for c in columns]

        buffer = []
        data = desc.get("data", [])

        for row in data:
            record = {}
            for key, value in zip(names, row):
                if col_types[key] == "date":
                    value = datetime.strptime(value, "%Y-%m-%d")
                record[key] = value
            buffer.append(record)

        if buffer:
            for row in buffer:
                self.engine.execute(table.insert(row))

        return table

    def create_date_dimension(self):
        """Creates and populates the date dimension"""

        table = sa.Table("dim_date", self.md,
                      # sa.Column("date_key",   sa.Integer, primary_key=True),
                      sa.Column("date_key",   sa.Integer),
                      sa.Column("date",       sa.DateTime),
                      sa.Column("year",       sa.Integer),
                      sa.Column("quarter",    sa.Integer),
                      sa.Column("month",      sa.Integer),
                      sa.Column("month_name", sa.String),
                      sa.Column("month_sname", sa.String),
                      sa.Column("day",        sa.Integer))

        self.md.create_all()

        start = date(2014,1,1)
        end = date(2016,12,31)

        current = start
        values = []
        insert = table.insert()

        while current <= end:
            current += timedelta(1)
            record = {
                "date_key": date_to_key(current),
                "date": current,
                "year": current.year,
                "quarter": month_to_quarter(current.month),
                "month": current.month,
                "month_name": current.strftime("%B"),
                "month_sname": current.strftime("%b"),
                "day": current.day
            }
            values.append(record)
            if len(values) > 100:
                for row in values:
                    self.engine.execute(insert.values(row))
                del values[:]

        for row in values:
            self.engine.execute(insert.values(row))

    def table(self, name):
        return sa.Table(name, self.md, autoload=True)

    def mapping_from_table(self, table_name, key_name, values):
        """Returns a dictionary constructed from table `table_name` where
        `key` is name of the key column (presumably unique) and `value` is
        name of a mapping values.

        Keys are ordered for nicer debugging."""

        mapping = OrderedDict()

        table = self.table(table_name)

        if not isinstance(values, (tuple, list)):
            values = (values, )
            multi = False
        else:
            multi = True

        selection = [table.c[key_name]] + [table.c[name] for name in values]

        select = sa.select(selection).order_by(table.c[key_name])

        result = self.engine.execute(select)
        for row in result:
            key = row[key_name]

            if multi:
                value = [row[col] for col in values]
            else:
                value = row[values[0]]

            mapping[key] = value

        return mapping

    def rows(self, table_name, columns=None):
        """Return an interable of rows from table `table_name`. If `columns`
        is specified then yield only those columns."""

        table = self.table(table_name)
        if columns:
            selection = [table.c[name] for name in columns]
        else:
            selection = table.columns

        select = sa.select(selection)

        return self.engine.execute(select)

    def insert(self, table_name, values):
        """Insert list of `values` into table `table_name`"""
        insert = self.table(table_name).insert()
        for row in values:
            self.engine.execute(insert, row)

    def dimension(self, table):
        """Returns a dimension lookup object for `table`."""
        rows = self.rows(table)
        return TinyDimension(self.table(table), rows)


class TinyDemoModelProvider(ModelProvider):
    def __init__(self, *args, **kwargs):
        path = os.path.join(os.path.dirname(__file__), "model.json")

        with open(path) as f:
            metadata = json.load(f)

        super(TinyDemoModelProvider, self).__init__(metadata)

    # TODO: improve this in the Provider class itself
    # def cube(self, name):
    #     cube = super(TinyDemoModelProvider, self).cube(name)
    #     return cube
    #     self.link

class TinyDimension(object):
    def __init__(self, table, rows):
        """Create a tiny dimension. First column of the table is assumed to be
        surrogate key and second column natural key.

        Note: At this moment, we don't assume versioned dimensions, therefore
        we might assume the natural key be as unique as the surrogate key.
        Distinction between the two is just for demonstrational purposes,
        regardles of their actual content.
        """
        self.rows = list(rows)
        self.values = {}
        self.natvalues = {}
        self.surkeys = {}

        surkey = list(table.columns)[0].name
        natkey = list(table.columns)[1].name

        for row in self.rows:
            self.values[row[surkey]] = row
            self.natvalues[row[natkey]] = row
            self.surkeys[row[natkey]] = row[surkey]

    def __getitem__(self, surkey):
        return self.values[surkey]

    def surrogate_key(self, natkey):
        return self.surkeys[natkey]


def date_to_key(date):
    """Converts `date` to date dimension key."""
    return int(date.strftime("%Y%m%d"))


def create_demo_dw(url, schema, recreate):
    dw = TinyDemoDataWarehouse(url, schema, recreate=recreate)

    if "CUBES_TEST_DB" in os.environ \
            and "CUBES_TEST_DB_REUSE" in os.environ:
        return dw

    dw.create_table(SRC_SALES)
    dw.create_table(DIM_CATEGORIES)
    dw.create_table(DIM_DEPARTMENTS)
    dw.create_table(DIM_ITEMS)
    dw.create_date_dimension()

    # Empty tables, will be filled below

    dw.create_table(FACT_SALES)
    dw.create_table(FACT_SALES_DENORM)

    # Create fact table(s)
    # --------------------
    # Create a star-schema fact table

    dim_item = dw.dimension("dim_item")
    dim_category = dw.dimension("dim_category")
    dim_department = dw.dimension("dim_department")

    ft_values = []
    dft_values = []
    for row in dw.rows("src_sales"):
        item = row["item"]
        item_key = dim_item.surrogate_key(item)
        category_key = dim_item[item_key]["category_key"]
        dept_key = dim_category[category_key]["department_key"]

        record = {
            "id": row["id"],
            "date_key": date_to_key(row["date"]),
            "item_key": item_key,
            "category_key": category_key,
            "department_key": dept_key,
            "quantity": row["quantity"],
            "price": row["price"],
            "discount": row["discount"]
        }
        ft_values.append(record)

        dft_record = {
            "date": row["date"],
            "item_name": item,
            "item_unit_price": dim_item[item_key]["unit_price"],
            "category_name": dim_category[category_key]["name"],
            "department_name": dim_department[dept_key]["name"],
        }

        record.update(dft_record)
        dft_values.append(record)

    dw.insert("fact_sales", ft_values)
    dw.insert("fact_sales_denorm", dft_values)

    return dw


if __name__ == "__main__":

    dw = create_demo_dw(
                    "postgres://localhost/cubes_test",
                    schema="test",
                    recreate=True)

