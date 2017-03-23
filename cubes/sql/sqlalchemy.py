"""Aliases for SQL/SQLAlchemy objects that are assured to be correctly
type-checked."""

from typing import (
        Any,
        Iterable,
        List,
        Mapping,
        TYPE_CHECKING,
        Tuple,
        Union,
    )

import sqlalchemy


# Engine
# ======
Engine = sqlalchemy.engine.base.Engine
Connection = sqlalchemy.engine.base.Connection
Connectable = sqlalchemy.engine.base.Connectable

ResultProxy = sqlalchemy.engine.result.ResultProxy
RowProxy = sqlalchemy.engine.result.RowProxy


# Schema
# ======
MetaData = sqlalchemy.sql.schema.MetaData
Column = sqlalchemy.sql.schema.Column
Table = sqlalchemy.sql.schema.Table

# Elements
# ========
ColumnElement = sqlalchemy.sql.elements.ColumnElement
and_ = sqlalchemy.sql.elements.and_
or_ = sqlalchemy.sql.elements.or_

# Selectables
# ===========
Select = sqlalchemy.sql.selectable.Select
FromClause = sqlalchemy.sql.selectable.FromClause


# Functions and Expressions
# =========================
extract = sqlalchemy.sql.expression.extract
func = sqlalchemy.sql.expression.func
join = sqlalchemy.sql.expression.join
select = sqlalchemy.sql.expression.select

# Exceptions
# ==========

NoSuchTableError = sqlalchemy.exc.NoSuchTableError
