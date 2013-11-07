# -*- coding=utf -*-

from ...logging import QueryLogHandler, QUERY_LOG_RECORD_ITEMS
from sqlalchemy import create_engine, Table, MetaData, Column
from sqlalchemy import Integer, Sequence, DateTime, String, Float
from sqlalchemy.exc import NoSuchTableError

class SQLQueryLogHandler(QueryLogHandler):
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
                Column('query', String),
                Column('cube', String),
                Column('cell', String),
                Column('identity', String),
                Column('elapsed_time', Float)
            ]
            self.table = Table(table, metadata, extend_existing=True, *columns)
            self.table.create()

    def write_record(self, record):
        row = dict(zip(QUERY_LOG_RECORD_ITEMS, record))
        insert = self.table.insert().values(row)
        self.engine.execute(insert)
