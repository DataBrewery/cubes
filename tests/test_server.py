# -*- coding=utf -*-
import unittest
from cubes import __version__
import json
from .common import CubesTestCaseBase
from sqlalchemy import MetaData, Table, Column, Integer, String

from werkzeug.test import Client
from werkzeug.wrappers import BaseResponse

from cubes.server import create_server
from cubes import compat
from cubes import Workspace

import csv


TEST_DB_URL = "sqlite:///"


class SlicerTestCaseBase(CubesTestCaseBase):
    def setUp(self):
        super(SlicerTestCaseBase, self).setUp()

        self.slicer = create_server()
        self.slicer.debug = True
        self.server = Client(self.slicer, BaseResponse)
        self.logger = self.slicer.logger
        self.logger.setLevel("DEBUG")

    def get(self, path, *args, **kwargs):
        if not path.startswith("/"):
            path = "/" + path

        response = self.server.get(path, *args, **kwargs)

        try:
            result = json.loads(compat.to_str(response.data))
        except ValueError:
            result = response.data

        return (result, response.status_code)

    def assertHasKeys(self, d, keys):
        for key in keys:
            self.assertIn(key, d)


class SlicerTestCase(SlicerTestCaseBase):
    def test_version(self):
        response, status = self.get("version")
        self.assertEqual(200, status)
        self.assertIsInstance(response, dict)
        self.assertIn("version", response)
        self.assertEqual(__version__, response["version"])

    def test_unknown(self):
        response, status = self.get("this_is_unknown")
        self.assertEqual(404, status)

@unittest.skip("We need to fix the model")
class SlicerModelTestCase(SlicerTestCaseBase):

    def setUp(self):
        super(SlicerModelTestCase, self).setUp()

        ws = Workspace()
        ws.register_default_store("sql", url=TEST_DB_URL)
        self.ws = ws
        self.slicer.cubes_workspace = ws

        # Satisfy browser with empty tables
        # TODO: replace this once we have data
        store = ws.get_store("default")
        table = Table("sales", store.metadata)
        table.append_column(Column("id", Integer))
        table.create()

        ws.import_model(self.model_path("model.json"))
        ws.import_model(self.model_path("sales_no_date.json"))

    def test_cube_list(self):
        response, status = self.get("cubes")
        self.assertIsInstance(response, list)
        self.assertEqual(2, len(response))

        for info in response:
            self.assertIn("name", info)
            self.assertIn("label", info)
            self.assertNotIn("dimensions", info)

        names = [c["name"] for c in response]
        self.assertCountEqual(["contracts", "sales"], names)

    def test_no_cube(self):
        response, status = self.get("cube/unknown_cube/model")
        self.assertEqual(404, status)
        self.assertIsInstance(response, dict)
        self.assertIn("error", response)
        # self.assertRegexpMatches(response["error"]["message"], "Unknown cube")

    def test_get_cube(self):
        response, status = self.get("cube/sales/model")
        import pdb; pdb.set_trace()
        self.assertEqual(200, status)
        self.assertIsInstance(response, dict)
        self.assertNotIn("error", response)

        self.assertIn("name", response)
        self.assertIn("measures", response)
        self.assertIn("aggregates", response)
        self.assertIn("dimensions", response)

        # We should not get internal info
        self.assertNotIn("mappings", response)
        self.assertNotIn("joins", response)
        self.assertNotIn("options", response)
        self.assertNotIn("browser_options", response)
        self.assertNotIn("fact", response)

        # Propert content
        aggregates = response["aggregates"]
        self.assertIsInstance(aggregates, list)
        self.assertEqual(4, len(aggregates))
        names = [a["name"] for a in aggregates]
        self.assertCountEqual(["amount_sum", "amount_min", "discount_sum",
                               "record_count"], names)

    def test_cube_dimensions(self):
        response, status = self.get("cube/sales/model")
        # Dimensions
        dims = response["dimensions"]
        self.assertIsInstance(dims, list)
        self.assertIsInstance(dims[0], dict)

        for dim in dims:
            self.assertIn("name", dim)
            self.assertIn("levels", dim)
            self.assertIn("default_hierarchy_name", dim)
            self.assertIn("hierarchies", dim)
            self.assertIn("is_flat", dim)
            self.assertIn("has_details", dim)

        names = [d["name"] for d in dims]
        self.assertCountEqual(["date", "flag", "product"], names)

        # Test dim flags
        self.assertEqual(True, dims[1]["is_flat"])
        self.assertEqual(False, dims[1]["has_details"])

        self.assertEqual(False, dims[0]["is_flat"])
        self.assertEqual(True, dims[0]["has_details"])


class SlicerAggregateTestCase(SlicerTestCaseBase):
    sql_engine = "sqlite:///"
    def setUp(self):
        super(SlicerAggregateTestCase, self).setUp()

        self.workspace = self.create_workspace(model="server.json")
        self.cube = self.workspace.cube("aggregate_test")
        self.slicer.cubes_workspace = self.workspace

        self.facts = Table("facts", self.metadata,
                        Column("id", Integer),
                        Column("id_date", Integer),
                        Column("id_item", Integer),
                        Column("amount", Integer)
                        )

        self.dim_date = Table("date", self.metadata,
                        Column("id", Integer),
                        Column("year", Integer),
                        Column("month", Integer),
                        Column("day", Integer)
                        )

        self.dim_item = Table("item", self.metadata,
                        Column("id", Integer),
                        Column("name", String)
                        )

        self.metadata.create_all()

        data = [
                    # Master-detail Match
                    ( 1, 20130901, 1,   20),
                    ( 2, 20130902, 1,   20),
                    ( 3, 20130903, 1,   20),
                    ( 4, 20130910, 1,   20),
                    ( 5, 20130915, 1,   20),
                    #             --------
                    #             ∑    100
                    # No city dimension
                    ( 6, 20131001, 2,  200),
                    ( 7, 20131002, 2,  200),
                    ( 8, 20131004, 2,  200),
                    ( 9, 20131101, 3,  200),
                    (10, 20131201, 3,  200),
                    #             --------
                    #             ∑   1000
                    #             ========
                    #             ∑   1100

                ]

        self.load_data(self.facts, data)

        data = [
                    (1, "apple"),
                    (2, "pear"),
                    (3, "garlic"),
                    (4, "carrod")
                ]

        self.load_data(self.dim_item, data)

        data = []
        for day in range(1, 31):
            row = (20130900+day, 2013, 9, day)
            data.append(row)

        self.load_data(self.dim_date, data)

    def test_aggregate_csv_headers(self):
        # Default = labels
        url = "cube/aggregate_test/aggregate?drilldown=date&format=csv"
        response, status = self.get(url)

        response = compat.to_str(response)
        reader = csv.reader(response.splitlines())
        header = next(reader)
        self.assertSequenceEqual(["Year", "Total Amount", "Item Count"],
                                 header)

        # Labels - explicit
        url = "cube/aggregate_test/aggregate?drilldown=date&format=csv&header=labels"
        response, status = self.get(url)

        response = compat.to_str(response)
        reader = csv.reader(response.splitlines())
        header = next(reader)
        self.assertSequenceEqual(["Year", "Total Amount", "Item Count"],
                                 header)
        # Names
        url = "cube/aggregate_test/aggregate?drilldown=date&format=csv&header=names"
        response, status = self.get(url)

        response = compat.to_str(response)
        reader = csv.reader(response.splitlines())
        header = next(reader)
        self.assertSequenceEqual(["date.year", "amount_sum", "count"],
                                 header)
        # None
        url = "cube/aggregate_test/aggregate?drilldown=date&format=csv&header=none"
        response, status = self.get(url)

        response = compat.to_str(response)
        reader = csv.reader(response.splitlines())
        header = next(reader)
        self.assertSequenceEqual(["2013", "100", "5"],
                                 header)
