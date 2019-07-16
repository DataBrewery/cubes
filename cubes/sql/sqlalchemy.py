"""Aliases for SQL/SQLAlchemy objects that are assured to be correctly
type-checked."""

from typing import TYPE_CHECKING, Any, Iterable, List, Mapping, Tuple, Union

import sqlalchemy

# Engine
# ======
Engine = sqlalchemy.engine.base.Engine
Connection = sqlalchemy.engine.base.Connection
Connectable = sqlalchemy.engine.base.Connectable
create_engine = sqlalchemy.engine.create_engine

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
not_ = sqlalchemy.sql.elements.not_

# Selectables
# ===========
Select = sqlalchemy.sql.selectable.Select
FromClause = sqlalchemy.sql.selectable.FromClause


# Functions and Expressions
# =========================

select = sqlalchemy.sql.expression.select
join = sqlalchemy.sql.expression.join

func = sqlalchemy.sql.expression.func
distinct = sqlalchemy.sql.expression.distinct
extract = sqlalchemy.sql.expression.extract
case = sqlalchemy.sql.expression.case

ReturnTypeFromArgs = sqlalchemy.sql.functions.ReturnTypeFromArgs
coalesce = sqlalchemy.sql.functions.coalesce
count = sqlalchemy.sql.functions.count
sum = sqlalchemy.sql.functions.sum
min = sqlalchemy.sql.functions.min
max = sqlalchemy.sql.functions.max

# Operators
# =========
le = sqlalchemy.sql.operators.le
lt = sqlalchemy.sql.operators.lt
ge = sqlalchemy.sql.operators.ge
gt = sqlalchemy.sql.operators.gt

# Exceptions
# ==========

NoSuchTableError = sqlalchemy.exc.NoSuchTableError
