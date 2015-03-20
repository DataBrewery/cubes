# -*- coding=utf -*-
"""SQL Expression compiler"""

# The compiler is meant to be maintained in a similar way as the star schema
# generator is – is to remain as much Cubes-independent as possible, just be a
# low level module somewhere between SQLAlchemy and Cubes.

import sqlalchemy.sql as sql

from expressions import Compiler

from ..errors import ExpressionError, InternalError


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

# TODO: Add: lstrip, rstrip, strip -> trim
# TODO: Add: like

# Add SQL-only aggregate functions here
# TODO: Add them
SQL_AGGREGATE_FUNCTIONS = []

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

        self._columns = columns or {}
        self.parameters = parameters or {}
        self.label = label

    def columns(self, attributes):
        """Get columns for `attributes`"""
        return [self._columns[attr] for attr in attributes]

    def column(self, ref):
        """Get a column expression for attribute with reference `ref`"""
        try:
            return self._columns[ref]
        except KeyError as e:
            # This should not happen under normal circumstances. If this
            # exception is raised, it very likely means that the owner of the
            # query contexts forgot to do something.
            raise InternalError("Missing column '{}'. Query context not "
                                "properly initialized or dependencies were "
                                "not correctly ordered?".format(ref))

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
        self._columns[name] = column


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

