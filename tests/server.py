import unittest

import sqlalchemy
from flask import Flask
from sqlalchemy import Table, Column, Integer, Float, String

import cubes
from cubes.backends import SnowflakeBrowser


class StarSQLTestCase(unittest.TestCase):
    def setUp(self):
        model_desc = {
            "cubes": [
                {
                    "name": "sales",
                    "measures": [
                        {"name": "amount", "aggregations": ["sum", "min"]},
                        "discount"
                    ],
                    "dimensions": ["date", "flag", "product"],
                    "details": ["fact_detail1", "fact_detail2"],
                    "joins": [
                        {"master": "sales.date_id", "detail": "dim_date.id"},
                        {"master": "sales.category_id",
                         "detail": "dim_category.id"},
                        {"master": "sales.product_id",
                         "detail": "dim_product.id"},
                    ],
                    "mappings": {
                        "product.name": "dim_product.product_name",
                        "date.month": "dim_date.month",
                        "date.month_name": "dim_date.month_name",
                        "date.month_sname": "dim_date.month_sname",
                        "date.day": "dim_date.day",
                        "date.year": "dim_date.year",
                        "date.id": "dim_date.id",
                        'product.id':'dim_product.id',
                         "product.category": "dim_product.category_id",
                        "product.category_name.en": "dim_category.category_name_en",
                        "product.category_name.sk": "dim_category.category_name_sk",
                        "product.subcategory": "dim_category.subcategory_id",
                        "product.subcategory_name.en": "dim_category.subcategory_name_en",
                        "product.subcategory_name.sk": "dim_category.subcategory_name_sk"
                    }
                }
            ],
            "dimensions": [
                {
                    "name": "date",
                    "levels": [
                        {"name": "year", "attributes": ["year"]},
                        {"name": "month", "attributes":
                            ["month", "month_name", "month_sname"]},
                        {"name": "day", "attributes": ["id", "day"]}
                    ],
                    "hierarchy": ["year", "month", "day"]
                },
                {"name": "flag"},
                {"name": "product",
                 "levels": [
                     {"name": "category",
                      "attributes": ["category",
                                     {"name": "category_name",
                                      "locales": ["en", "sk"]}
                      ]
                     },
                     {"name": "subcategory",
                      "attributes": ["subcategory",
                                     {"name": "subcategory_name",
                                      "locales": ["en", "sk"]}
                      ]
                     },
                     {"name": "product",
                      "attributes": ["id",
                                     {"name": "name"}
                      ],
                     }
                 ]
                }
            ]
        }

        engine = sqlalchemy.create_engine('sqlite://')
        self.connection = engine.connect()
        metadata = sqlalchemy.MetaData()
        metadata.bind = engine

        sales = Table('sales', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('amount', Float),
                      Column('discount', Float),
                      Column('fact_detail1', String),
                      Column('fact_detail2', String),
                      Column('flag', String),
                      Column('date_id', Integer),
                      Column('product_id', Integer),
                      Column('category_id', Integer)
        )

        date = Table('dim_date', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('day', Integer),
                      Column('month', Integer),
                      Column('month_name', String),
                      Column('month_sname', String),
                      Column('year', Integer)
        )

        product = Table('dim_product', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('category_id', Integer),
                      Column('product_name', String),
        )

        category = Table('dim_category', metadata,
                      Column('id', Integer, primary_key=True),
                      Column('category_name_en', String),
                      Column('category_name_sk', String),
                      Column('subcategory_id', Integer),
                      Column('subcategory_name_en', String),
                      Column('subcategory_name_sk', String)
        )

        metadata.create_all(engine)
        self.metadata = metadata

        self.connection.execute(category.insert().values(id=1))
        self.connection.execute(product.insert().values(id=1, category_id=1))
        self.connection.execute(date.insert().values(id=1))
        self.connection.execute(sales.insert().values(product_id=1, date_id=1, category_id=1))

        self.model = cubes.create_model(model_desc)
        self.cube = self.model.cube("sales")
        self.browser = SnowflakeBrowser(self.cube, connectable=self.connection,
                                        dimension_prefix="dim_")
        self.browser.debug = True
        self.cube.fact = 'sales'
        self.mapper = self.browser.mapper

class FlaskTest(StarSQLTestCase):
    def setUp(self):
        super(FlaskTest, self).setUp()
        engine = sqlalchemy.create_engine('sqlite://')
        workspace = cubes.create_workspace('sql', self.model, engine=self.connection)


        self.app = Flask(__name__)
        self.app.register_blueprint(cubes.server.slicer_blueprint)
        self.app.workspace = workspace
        self.client = self.app.test_client()

    def test_urls(self):
        urls = ['/', '/version', '/locales', '/model', '/model/cubes',
                '/model/cube', '/model/cube/sales', '/model/cube/sales/dimensions',
                '/model/dimension/date', '/model/dimension/date/levels',
               '/model/dimension/date/level_names',
               '/cube/sales/aggregate', '/cube/sales/facts',
               '/cube/sales/fact/1']
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(200, response.status_code,
                             msg='Invalid url: %r' % url)