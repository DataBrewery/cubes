import sqlalchemy
import csv

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
                 "float":sqlalchemy.Float,
                 "string":sqlalchemy.String(256) }

    if create_id:
        col = sqlalchemy.schema.Column('id', sqlalchemy.Integer, primary_key=True)
        table.append_column(col)
    
    field_names = []
    for (field_name, field_type) in fields:
        col = sqlalchemy.schema.Column(field_name, type_map[field_type.lower()])
        table.append_column(col)
        field_names.append(field_name)

    table.create()

    reader = csv.reader(open(file_name))
    
    # Skip header
    reader.next()

    insert_command = table.insert()
    
    for row in reader:
        record = dict(zip(field_names, row))
        insert_command.execute(record)
