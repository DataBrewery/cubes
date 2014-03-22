# -*- coding: utf-8 -*-

from .errors import ExpressionError

__all__ = [
    "evaluate_expression"
]


def evaluate_expression(expression, context=None, role='expr', expected=None):
    compiled_expr = compile(expression, ('__%s__' % role), 'eval')
    context = context or {}

    result = eval(compiled_expr, context)

    if expected is not None and not isinstance(result, expected):
        raise ExpressionError("Cannot evaluate a %s object from "
                              "reference's %s expression: %r"
                              % (expected, role, expression))
    return result
