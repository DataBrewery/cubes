# -*- coding=utf -*-

from __future__ import absolute_import

from ...server.logging import RequestLogHandler, REQUEST_LOG_ITEMS
from sqlalchemy import create_engine, Table, MetaData, Column
from sqlalchemy import Integer, Sequence, DateTime, String, Float
from sqlalchemy.exc import NoSuchTableError
from ...browser import Drilldown
from .store import create_sqlalchemy_engine

import logging

class SQLRequestLogHandler(RequestLogHandler):
    def __init__(self, url=None, table=None, dimensions_table=None, **options):

        self.url = url
        self.engine = create_sqlalchemy_engine(url, options)

        metadata = MetaData(bind=self.engine)

        logging.getLogger('sqlalchemy.engine').setLevel("DEBUG")
        logging.getLogger('sqlalchemy.pool').setLevel("DEBUG")

        try:
            self.table = Table(table, metadata, autoload=True)

        except NoSuchTableError:
            columns = [
                Column('id', Integer, Sequence(table+"_seq"),
                       primary_key=True),
                Column('timestamp', DateTime),
                Column('method', String(50)),
                Column('cube', String(250)),
                Column('cell', String(2000)),
                Column('identity', String(250)),
                Column('elapsed_time', Float),
                Column('attributes', String(2000)),
                Column('split', String(2000)),
                Column('drilldown', String(2000)),
                Column('page', Integer),
                Column('page_size', Integer),
                Column('format', String(50)),
                Column('header', String(50)),
            ]

            self.table = Table(table, metadata, extend_existing=True, *columns)
            self.table.create()

        # Dimensions table: use of dimensions
        # Used-as: cut, split, drilldown
        # Value:
        #     cut: cut value
        #     split: cut value

        if dimensions_table:
            try:
                self.dims_table = Table(dimensions_table, metadata, autoload=True)

            except NoSuchTableError:
                columns = [
                    Column('id', Integer, Sequence(table+"_seq"),
                           primary_key=True),
                    Column('query_id', Integer),
                    Column('dimension', String(250)),
                    Column('hierarchy', String(250)),
                    Column('level', String(250)),
                    Column('used_as', String(50)),
                    Column('value', String(2000)),
                ]

                self.dims_table = Table(dimensions_table, metadata, extend_existing=True, *columns)
                self.dims_table.create()
        else:
            self.dims_table = None

    def write_record(self, cube, cell, record):
        drilldown = record.get("drilldown")

        if drilldown is not None:
            if cell:
                drilldown = Drilldown(drilldown, cell)
                record["drilldown"] = str(drilldown)
            else:
                drilldown = []
                record["drilldown"] = None

        connection = self.engine.connect()
        trans = connection.begin()

        insert = self.table.insert().values(record)
        result = connection.execute(insert)
        query_id = result.inserted_primary_key[0]

        if self.dims_table is not None:
            uses = []

            cuts = cell.cuts if cell else []
            cuts = cuts or []

            for cut in cuts:
                dim = cube.dimension(cut.dimension)
                depth = cut.level_depth()
                if depth:
                    level = dim.hierarchy(cut.hierarchy)[depth-1]
                    level_name = str(level)
                else:
                    level_name = None

                use = {
                    "query_id": query_id,
                    "dimension": str(dim),
                    "hierarchy": str(cut.hierarchy),
                    "level": str(level_name),
                    "used_as": "cell",
                    "value": str(cut)
                }
                uses.append(use)

            if drilldown:
                for item in drilldown:
                    (dim, hier, levels) = item[0:3]
                    if levels:
                        level = str(levels[-1])
                    else:
                        level = None

                    use = {
                        "query_id": query_id,
                        "dimension": str(dim),
                        "hierarchy": str(hier),
                        "level": str(level),
                        "used_as": "drilldown",
                        "value": None
                    }
                    uses.append(use)


            if uses:
                insert = self.dims_table.insert().values(uses)
                connection.execute(insert)

        trans.commit()
        connection.close()

