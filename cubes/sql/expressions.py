# -*- coding=utf -*-
"""SQL Expression compiler"""

# The compiler is meant to be maintained in a similar way as the star schema
# generator is – is to remain as much Cubes-independent as possible, just be a
# low level module somewhere between SQLAlchemy and Cubes.

from __future__ import absolute_import

import sqlalchemy.sql as sql

from expressions import Compiler
from .functions import get_aggregate_function

from ..errors import ExpressionError


__all__ = [
    "SQLExpressionContext",
    "compile_attributes",
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

# TODO: Add: lstrip, rstrip, strip -> trim
# TODO: Add: like

SQL_AGGREGATE_FUNCTIONS = [
    "sum", "min", "max", "avg", "stddev", "variance", "count"
]

SQL_ALL_FUNCTIONS = SQL_FUNCTIONS + SQL_AGGREGATE_FUNCTIONS;

SQL_VARIABLES = [
    "current_date", "current_time", "local_date", "local_time"
]


class SQLExpressionContext(object):
    """Context used for building a list of all columns to be used within a
    single SQL query."""

    def __init__(self, columns=None, parameters=None, label=None):
        """Creates a SQL expression compiler context.

        * `bases` is a dictionary of base columns or column expressions
        * `for_aggregate` is a flag where `True` means that the expression is
          expected to be an aggregate expression
        * `label` is just informative context label to be used for debugging
          purposes or in an exception. Can be a cube name or a dimension
          name.
        """

        if columns:
            self._columns = dict(columns)
        else:
            self._columns = {}
        self.parameters = parameters or {}
        self.label = label

    @property
    def columns(self):
        return self._columns

    def resolve(self, variable):
        """Resolve `variable` – return either a column, variable from a
        dictionary or a SQL constant (in that order)."""

        if variable in self._columns:
            return self._columns[variable]

        elif variable in self.parameters:
            result = self.parameters[variable]

        elif variable in SQL_VARIABLES:
            result = getattr(sql.func, variable)()

        else:
            label = " in {}".format(self.label) if self.label else ""
            raise ExpressionError("Unknown attribute, variable or parameter "
                                  "'{}'{}" .format(variable, label))

        return result

    def __getitem__(self, item):
        return self.resolve(item)

    def function(self, name):
        """Return a SQL function"""
        if name not in SQL_ALL_FUNCTIONS:
            raise ExpressionError("Unknown function '{}'"
                                  .format(name))
        return getattr(sql.func, name)

    def add_column(self, name, column):
        self._columns[name] = column


def compile_attributes(bases, dependants, parameters, coalesce=None,
                       label=None):
    """Compile dependant attributes in `dependants`. `bases` is a dictionary
    of base attributes and their column expressions."""

    context = SQLExpressionContext(bases, parameters, label=label)
    compiler = SQLExpressionCompiler()

    for attr in dependants:
        # TODO: remove this hasattr with something nicer
        if hasattr(attr, "function") and attr.function:
            # Assumption: only aggregates have function, no measures or other
            # attributes (important!)
            #
            # Aggregation function names are case in-sensitive.
            #
            # If `coalesce_measure` is `True` then selected measure column is
            # wrapped in ``COALESCE(column, 0)``.

            function_name = attr.function.lower()
            function = get_aggregate_function(function_name)
            column = function(attr, context, coalesce)
        else:
            column = compiler.compile(attr.expression, context)

        context.add_column(attr.ref, column)

    return context.columns


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
            result = (- operand)
        elif operator == "+":
            result = (+ operand)
        elif operator == "~":
            result = (~ operand)
        elif operator == "not":
            result = sql.expression.not_(operand)
        else:
            raise SyntaxError("Unknown unary operator '%s'" % operator)

        return result

    def compile_function(self, context, func, args):
        func = context.function(func.name)
        return func(*args)

