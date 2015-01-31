"""Cubes SQL backend utilities, mostly to be used by the slicer command."""

from sqlalchemy.sql.expression import Executable, ClauseElement
from sqlalchemy.ext.compiler import compiles
import sqlalchemy.sql as sql

__all__ = [
    "CreateTableAsSelect",
    "InsertIntoAsSelect",
    "CreateOrReplaceView",
    "condition_conjunction",
    "order_column"
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
@compiles(CreateTableAsSelect, "sqlite")
def visit_create_table_as_select(element, compiler, **kw):
    preparer = compiler.dialect.preparer(compiler.dialect)
    full_name = preparer.format_table(element.table)

    return "CREATE TABLE %s AS %s" % (
        element.table,
        compiler.process(element.select)
    )

class CreateOrReplaceView(Executable, ClauseElement):
    def __init__(self, view, select):
        self.view = view
        self.select = select

@compiles(CreateOrReplaceView)
def visit_create_or_replace_view(element, compiler, **kw):
    preparer = compiler.dialect.preparer(compiler.dialect)
    full_name = preparer.format_table(element.view)

    return "CREATE OR REPLACE VIEW %s AS (%s)" % (
        full_name,
        compiler.process(element.select)
    )

@compiles(CreateOrReplaceView, "sqlite")
def visit_create_or_replace_view(element, compiler, **kw):
    preparer = compiler.dialect.preparer(compiler.dialect)
    full_name = preparer.format_table(element.view)

    return "CREATE VIEW %s AS %s" % (
        full_name,
        compiler.process(element.select)
    )

@compiles(CreateOrReplaceView, "mysql")
def visit_create_or_replace_view(element, compiler, **kw):
    preparer = compiler.dialect.preparer(compiler.dialect)
    full_name = preparer.format_table(element.view)

    return "CREATE OR REPLACE VIEW %s AS %s" % (
        full_name,
        compiler.process(element.select)
    )

class InsertIntoAsSelect(Executable, ClauseElement):
    def __init__(self, table, select, columns=None):
        self.table = table
        self.select = select
        self.columns = columns


@compiles(InsertIntoAsSelect, "mysql")
def visit_insert_into_as_select(element, compiler, **kw):
    preparer = compiler.dialect.preparer(compiler.dialect)
    full_name = preparer.format_table(element.table)

    if element.columns:
        qcolumns = [preparer.format_column(c) for c in element.columns]
        col_list = "(%s) " % ", ".join([str(c) for c in qcolumns])
    else:
        col_list = ""

    stmt = "INSERT INTO %s %s %s" % (
        full_name,
        col_list,
        compiler.process(element.select)
    )

    return stmt


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


def condition_conjunction(conditions):
    """Do conjuction of conditions if there are more than one, otherwise just
    return the single condition."""
    if not conditions:
        return None
    elif len(conditions) == 1:
        return conditions[0]
    else:
        return sql.expression.and_(*conditions)


def order_column(column, order):
    """Orders a `column` according to `order` specified as string."""

    if not order:
        return column
    elif order.lower().startswith("asc"):
        return column.asc()
    elif order.lower().startswith("desc"):
        return column.desc()
    else:
        raise ArgumentError("Unknown order %s for column %s") % (order, column)

