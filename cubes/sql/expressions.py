# -*- coding=utf -*-

from ..expressions import ExpressionCompiler, Variable
from ..expressions import STANDARD_AGGREGATE_FUNCTIONS
from ..errors import ExpressionError
import sqlalchemy.sql as sql

SQL_FUNCTIONS = [
    # String
    "lower", "upper", "left", "right", "substr",
    "lpad", "rpad", "replace",
    "concat", "repeat", "position",

    # Math
    "round", "trunc", "floor", "ceil",
    "mod", "remainder",
    "sign",

    "pow", "exp", "log", "log10",
    "sqrt",
    "cos", "sin", "tan",

    # Date/time
    "extract",

    # Conditionals
    "coalesce", "nullif", "case",

    # TODO: add map(value, match1, result1, match2, result2, ..., default)
    # "map",
]

# TODO: lstrip, rstrip, strip -> trim
# TODO: like

# Add SQL-only aggregate functions here
# TODO: Add these
SQL_AGGREGATE_FUNCTIONS = STANDARD_AGGREGATE_FUNCTIONS + []

SQL_ALL_FUNCTIONS = SQL_FUNCTIONS + SQL_AGGREGATE_FUNCTIONS;

SQL_VARIABLES = [
    "current_date", "current_time", "local_date", "local_time"
]


class SQLExpressionContext(object):
    def __init__(self, cube, getter, for_aggregate=False, parameters=None):
        """Creates a SQL expression compiler context for `cube`. `getter` is
        a base column getter function that takes one argument: logical
        attribute reference. `aggregate` is a flag where `True` means that the
        expression is expected to be an aggregate expression."""

        self.cube = cube
        self.for_aggregate = for_aggregate
        self.getter = getter
        self.parameters = parameters or {}

        if for_aggregate:
            self.attributes = cube.all_aggregate_attributes
        else:
            self.attributes = cube.all_attributes

        self.attribute_names = [attr.ref for attr in self.attributes]
        self.resolved = {}

    def resolve(self, name):
        """Resolve variable `name` – return either a column, variable from a
        dictionary or a SQL constant (in that order)."""

        if name in self.resolved:
            return self.resolved[name]

        elif name in self.attribute_names:
            # Get the raw column
            result = self.getter(name)

        elif name in self.parameters:
            result = self.parameters[name]

        elif name in SQL_VARIABLES:
            result = getattr(sql.func, name)()

        else:
            raise ExpressionError("Unknown expression variable '{}' "
                                  "in cube {}".format(name, cube))

        self.resolved[name] = result
        return result

    def function(self, name):
        """Return a SQL function"""
        # TODO: check for function existence (allowed functions)
        sql_func = getattr(sql.func, func)
        return sql_func(*args)


class SQLExpressionCompiler(ExpressionCompiler):
    def __init__(self, context):
        super(SQLExpressionCompiler, self).__init__(context)

    def compile_operator(self, context, operator, op1, op2):
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
        name = operand.name
        result = self.context.resolve(name)
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
        return func(**args)


