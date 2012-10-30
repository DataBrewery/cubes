"""Cubes SQL backend utilities, mostly to be used by the slicer command."""

from sqlalchemy.sql.expression import Executable, ClauseElement
from sqlalchemy.ext.compiler import compiles

__all__ = [
        "CreateTableAsSelect",
        "InsertIntoAsSelect"
        ]

class CreateTableAsSelect(Executable, ClauseElement):
    def __init__(self, table, select):
        self.table = table
        self.select = select

@compiles(CreateTableAsSelect)
def visit_create_table_as_select(element, compiler, **kw):
    preparer = compiler.dialect.preparer(compiler.dialect)
    full_name = preparer.format_table(element.table)

    return "CREATE TABLE %s AS (%s)" % (
        element.table,
        compiler.process(element.select)
    )

class InsertIntoAsSelect(Executable, ClauseElement):
    def __init__(self, table, select, columns=None):
        self.table = table
        self.select = select
        self.columns = columns

@compiles(InsertIntoAsSelect)
def visit_insert_into_as_select(element, compiler, **kw):
    preparer = compiler.dialect.preparer(compiler.dialect)
    full_name = preparer.format_table(element.table)

    if element.columns:
        qcolumns = [preparer.format_column(c) for c in element.columns]
        col_list = "(%s) " % ", ".join([str(c) for c in qcolumns])
    else:
        col_list = ""

    stmt = "INSERT INTO %s %s(%s)" % (
        full_name,
        col_list,
        compiler.process(element.select)
    )

    return stmt

def validate_physical_schema(url, model, fact_prefix=None, dimension_prefix=None):
    """Validate the model and mappings against physical schema - check for 
    existence of each column."""

    pass

def denormalize_locale(connection, localized, dernomralized, locales):
    """Create denormalized version of localized table. (not imlpemented, just proposal)

    Type 1:

    Localized table: id, locale, field1, field2, ...

    Denomralized table: id, field1_loc1, field1_loc2, field2_loc1, field2_loc2,...

    Type 2:

    Localized table: id, locale, key, field, content

    Denomralized table: id, field1_loc1, field1_loc2, field2_loc1, field2_loc2,...


    """
    pass
