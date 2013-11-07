# -*- coding=utf -*-

from ...server.logging import RequestLogHandler, REQUEST_LOG_ITEMS
from sqlalchemy import create_engine, Table, MetaData, Column
from sqlalchemy import Integer, Sequence, DateTime, String, Float
from sqlalchemy.exc import NoSuchTableError

class SQLRequestLogHandler(RequestLogHandler):
    def __init__(self, url=None, table=None, **options):

        self.url = url
        self.engine = create_engine(url)

        metadata = MetaData(bind=self.engine)

        try:
            self.table = Table(table, metadata, autoload=True)

        except NoSuchTableError:
            columns = [
                Column('id', Integer, Sequence(table+"_seq"),
                       primary_key=True),
                Column('timestamp', DateTime),
                Column('method', String),
                Column('cube', String),
                Column('cell', String),
                Column('identity', String),
                Column('elapsed_time', Float),
                Column('attributes', String),
                Column('split', String),
                Column('drilldown', String),
                Column('page', Integer),
                Column('page_size', Integer),
                Column('format', String),
                Column('headers', String),
            ]

            self.table = Table(table, metadata, extend_existing=True, *columns)
            self.table.create()

    def write_record(self, record):
        insert = self.table.insert().values(record)
        self.engine.execute(insert)
