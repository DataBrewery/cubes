# -*- coding: utf-8 -*-

import sqlalchemy
import csv
import csv, codecs, cStringIO

class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")

class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self

def create_table_from_csv(connectable, file_name, table_name, fields, create_id = False, schema = None):
    """Create a table with name `table_name` from a CSV file `file_name` with columns corresponding
    to `fields`. The `fields` is a list of two string tuples: (name, type) where type might be:
    ``integer``, ``float`` or ``string``.
    
    If `create_id` is ``True`` then a column with name ``id`` is created and will contain generated
    sequential record id.
    
    This is just small utility function for sandbox, play-around and testing purposes. It is not
    recommended to be used for serious CSV-to-table loadings. For more advanced CSV loadings use another
    framework, such as Brewery (http://databrewery.org).
    """

    metadata = sqlalchemy.MetaData(bind = connectable)

    table = sqlalchemy.Table(table_name, metadata, autoload=False, schema=schema)
    if table.exists():
        table.drop(checkfirst=False)

    type_map = { "integer": sqlalchemy.Integer,
                 "float":sqlalchemy.Numeric,
                 "string":sqlalchemy.String(256),
                 "text":sqlalchemy.Text,
                 "date":sqlalchemy.Text,
                 "boolean": sqlalchemy.Integer }

    if create_id:
        col = sqlalchemy.schema.Column('id', sqlalchemy.Integer, primary_key=True)
        table.append_column(col)
    
    field_names = []
    for (field_name, field_type) in fields:
        col = sqlalchemy.schema.Column(field_name, type_map[field_type.lower()])
        table.append_column(col)
        field_names.append(field_name)

    table.create()

    reader = UnicodeReader(open(file_name))
    
    # Skip header
    reader.next()

    insert_command = table.insert()
    
    for row in reader:
        record = dict(zip(field_names, row))
        insert_command.execute(record)
