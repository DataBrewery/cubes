# -*- coding=utf -*-

from .errors import BrowserError
import datetime
import re

try:
    import sqlalchemy
    import sqlalchemy.sql as sql

except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")


__all__ = [
    "evaluate_expression"
]

_EXPR_EVAL_NS = {
    "sqlalchemy": sqlalchemy,
    "sql": sql,
    "func": sql.expression.func,
    "case": sql.expression.case,
    "text": sql.expression.text,
    "datetime": datetime,
    "re": re,
    "extract": sql.expression.extract,
    "and_": sql.expression.and_,
    "or_": sql.expression.or_
}


def evaluate_expression(expression, global_bindings, bindings={}, role='expr', expected=None):
    compiled_expr = compile(expression, ('__%s__' % role), 'eval')
    context = {}
    context.update(global_bindings)
    context.update(bindings)

    result = eval(compiled_expr, context)

    if expected is not None:
        if not isinstance(result, expected):
            raise BrowserError("Cannot evaluate a %s object from "
                               "reference's %s expression: %r" % (expected, role, expression))
    return result
