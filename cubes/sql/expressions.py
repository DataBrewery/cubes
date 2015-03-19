# -*- coding=utf -*-

import sqlalchemy.sql as sql

from expressions import Compiler, Variable
from collections import OrderedDict

from ..errors import ExpressionError

__all__ = [
    "SQLQueryContext",
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


class SQLQueryContext(object):
    """Context used for building a list of all columns to be used within a
    single SQL query."""

    def __init__(self, bases, for_aggregate=False,
                 parameters=None, label=None):
        """Creates a SQL expression compiler context.

        * `bases` is a dictionary of base columns or column expressions
        * `for_aggregate` is a flag where `True` means that the expression is
          expected to be an aggregate expression
        * `label` is just informative context label to be used for debugging
          purposes or in an exception. Can be a cube name or a dimension
          name.
        """

        self.bases = bases
        self.for_aggregate = for_aggregate

        self.parameters = parameters or {}

        self.label = label

        # Columns after compilation
        self.columns = {}

    def resolve(self, variable):
        """Resolve `variable` – return either a column, variable from a
        dictionary or a SQL constant (in that order)."""

        if variable in self.columns:
            return self.columns[variable]
        elif variable in self.bases:
            # Get the raw column
            result = self.bases[variable]

        elif variable in self.parameters:
            result = self.parameters[variable]

        elif variable in SQL_VARIABLES:
            result = getattr(sql.func, variable)()

        else:
            label = " in {}".format(self.label) if self.label else ""
            raise ExpressionError("Unknown expression variable '{}'{}"
                                  .format(variable, label))

        return result

    def function(self, name):
        """Return a SQL function"""
        if name not in SQL_FUNCTIONS:
            raise ExpressionError("Unknown function '{}'"
                                  .format(name))
        return getattr(sql.func, name)

    def add_column(self, name, column):
        self.columns[name] = column


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

