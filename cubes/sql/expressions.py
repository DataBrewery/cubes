# -*- coding=utf -*-
"""SQL Expression compiler"""

# The compiler is meant to be maintained in a similar way as the star schema
# generator is – is to remain as much Cubes-independent as possible, just be a
# low level module somewhere between SQLAlchemy and Cubes.

import sqlalchemy.sql as sql

from expressions import Compiler, Variable
from collections import OrderedDict

from ..errors import ExpressionError

__all__ = [
    "SQLExpressionContext",
    "SQLExpressionCompiler",
]


SQL_FUNCTIONS = [
    # String
    "lower", "upper", "left", "right", "substr",
    "lpad", "rpad", "replace",
    "concat", "repeat", "position",

    # Math
    "round", "trunc", "floor", "ceil",
    "mod", "remainder",
    "sign",

    "min", "max",

    "pow", "exp", "log", "log10",
    "sqrt",
    "cos", "sin", "tan",

    # Date/time
    "extract",

    # Conditionals
    "coalesce", "nullif", "case",

]

# TODO: lstrip, rstrip, strip -> trim
# TODO: like

# Add SQL-only aggregate functions here
# TODO: Add these
SQL_AGGREGATE_FUNCTIONS = []

SQL_ALL_FUNCTIONS = SQL_FUNCTIONS + SQL_AGGREGATE_FUNCTIONS;

SQL_VARIABLES = [
    "current_date", "current_time", "local_date", "local_time"
]


class SQLExpressionCompiler(Compiler):
    def __init__(self, context=None):
        super(SQLExpressionCompiler, self).__init__(context)

    def compile_literal(self, context, literal):
        return sql.expression.bindparam("literal",
                                        literal,
                                        unique=True)

    def compile_binary(self, context, operator, op1, op2):
        if operator == "*":
            result = op1 * op2
        elif operator == "/":
            result = op1 / op2
        elif operator == "%":
            result = op1 % op2
        elif operator == "+":
            result = op1 + op2
        elif operator == "-":
            result = op1 - op2
        elif operator == "&":
            result = op1 & op2
        elif operator == "|":
            result = op1 | op2
        elif operator == "<":
            result = op1 < op2
        elif operator == "<=":
            result = op1 <= op2
        elif operator == ">":
            result = op1 > op2
        elif operator == ">=":
            result = op1 >= op2
        elif operator == "=":
            result = op1 == op2
        elif operator == "!=":
            result = op1 != op2
        elif operator == "and":
            result = sql.expression.and_(op1, op2)
        elif operator == "or":
            result = sql.expression.or_(op1, op2)
        else:
            raise SyntaxError("Unknown operator '%s'" % operator)

        return result

    def compile_variable(self, context, variable):
        name = variable.name
        result = context.resolve(name)
        return result

    def compile_unary(self, context, operator, operand):
        if operator == "-":
            result =  (- operand)
        elif operator == "+":
            result =  (+ operand)
        elif operator == "~":
            result =  (~ operand)
        elif operator == "not":
            result = sql.expression.not_(operand)
        else:
            raise SyntaxError("Unknown unary operator '%s'" % operator)

        return result

    def compile_function(self, context, func, args):
        func = context.function(func.name)
        return func(*args)

