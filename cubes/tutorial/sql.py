# -*- coding: utf-8 -*-

import sqlalchemy
import csv
import codecs
from cubes import compat


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        assert 'b' in f.mode, "in py3k, codec's StreamReader needs a bytestream"
        self.reader = codecs.getreader(encoding)(f)
        self.next = self.__next__
    def __iter__(self):
        return self

    def __next__(self):
        return compat.to_unicode(next(self.reader))


class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)
        self.next = self.__next__

    def __next__(self):
        row = next(self.reader)
        return [compat.to_unicode(s) for s in row]

    def __iter__(self):
        return self


def create_table_from_csv(connectable, file_name, table_name, fields,
                          create_id=False, schema=None):
    """Create a table with name `table_name` from a CSV file `file_name` with columns corresponding
    to `fields`. The `fields` is a list of two string tuples: (name, type) where type might be:
    ``integer``, ``float`` or ``string``.

    If `create_id` is ``True`` then a column with name ``id`` is created and will contain generated
    sequential record id.

    This is just small utility function for sandbox, play-around and testing purposes. It is not
    recommended to be used for serious CSV-to-table loadings. For more advanced CSV loadings use another
    framework, such as Brewery (http://databrewery.org).
    """

    metadata = sqlalchemy.MetaData(bind=connectable)

    table = sqlalchemy.Table(table_name, metadata, autoload=False, schema=schema)
    if table.exists():
        table.drop(checkfirst=False)

    type_map = {"integer": sqlalchemy.Integer,
                "float": sqlalchemy.Numeric,
                "string": sqlalchemy.String(256),
                "text": sqlalchemy.Text,
                "date": sqlalchemy.Text,
                "boolean": sqlalchemy.Integer}

    if create_id:
        col = sqlalchemy.schema.Column('id', sqlalchemy.Integer, primary_key=True)
        table.append_column(col)

    field_names = []
    for (field_name, field_type) in fields:
        col = sqlalchemy.schema.Column(field_name, type_map[field_type.lower()])
        table.append_column(col)
        field_names.append(field_name)

    table.create()

    reader = UnicodeReader(open(file_name, 'rb'))

    # Skip header
    next(reader)

    insert_command = table.insert()

    for row in reader:
        record = dict(zip(field_names, row))
        insert_command.execute(record)
