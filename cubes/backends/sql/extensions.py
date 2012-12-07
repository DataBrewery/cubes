try:
    import sqlalchemy
    import sqlalchemy.sql as sql
    from sqlalchemy.sql.functions import ReturnTypeFromArgs
except ImportError:
    from cubes.common import MissingPackage
    sqlalchemy = sql = MissingPackage("sqlalchemy", "SQL aggregation browser")
    missing_error = MissingPackage("sqlalchemy", "SQL browser extensions")

    class ReturnTypeFromArgs(object):
        def __init__(*args, **kwargs):
            # Just fail by trying to call missing package
            missing_error()

class avg(ReturnTypeFromArgs):
    pass

# Works with PostgreSQL
class stddev(ReturnTypeFromArgs):
    pass

class variance(ReturnTypeFromArgs):
    pass

