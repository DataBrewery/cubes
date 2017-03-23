"""Physical Metadata"""

from typing import Any, List, Optional, Hashable, NamedTuple
from enum import Enum

from ..types import JSONType
from ..common import list_hash
from ..errors import ArgumentError


# TODO: [typing] Make JoinMethod enum
class JoinMethod(Enum):
    default = 0
    match = 1
    master = 2
    detail = 3


class JoinKey(Hashable):
    schema: Optional[str]
    table: Optional[str]
    columns: Optional[List[str]]

    def __init__(self,
            columns: Optional[List[str]],
            table: Optional[str]=None,
            schema: Optional[str]=None,
            ) -> None:
        self.columns = columns
        self.table = table
        self.schema = schema

    @classmethod
    def from_dict(cls, obj: JSONType) -> "JoinKey":
        """Utility function that will create JoinKey from multiple types of
        JSON representations:

        * string with optional schema and table in format
          ``[[schema.]table.]column``
        * dictionary with keys `schema`, `table`, `column` or `columns`

        Note that Cubes at this low level does not know which table is used for
        a dimension, therefore the default dimension schema from mapper's
        naming can not be assumed here and has to be explicitly mentioned.
        """

        table: Optional[str]
        schema: Optional[str]
        columns: Optional[List[str]]

        # FIXME: [typing] How this can be used? Investigate downstream.
        if obj is None:
            return JoinKey(None, None, None)

        # TODO: Legacy - deprecated
        if isinstance(obj, (list, tuple)):
            raise Exception(f"Join key specified as a list/tuple. "
                            f"should be a dictionary: '{obj}'")

        if isinstance(obj, str):
            split: List[Optional[str]]
            split = obj.split(".")
            if len(split) > 3:
                raise Exception("Join key `{obj}` has too many components.")
            split = [None] * (3 - len(split)) + split

            schema = split[0]
            table = split[1]
            columns = [split[2]]
        else:
            schema = obj.get("schema")
            table = obj.get("table")
            if "columns" in obj:
                columns = obj["columns"]
            elif "column" in obj:
                columns = [obj["column"]]
            else:
                columns = []

        return JoinKey(columns= columns, table= table, schema= schema)

    def __hash__(self) -> int:
        column_hash: int

        if self.columns is not None:
            # TODO: This requires python/mypy#1746
            column_hash = list_hash(self.columns)  # type: ignore
        else:
            column_hash = 0

        return hash(self.schema) ^ hash(self.table) ^ column_hash

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, JoinKey):
            return False
        else:
            return self.columns == other.columns \
                    and self.table == other.table \
                    and self.schema == other.schema

# FIXME: Put this string into the named tuple below (requires python/mypy#3043)

"""Table join specification. `master` and `detail` are TableColumnReference
tuples. `method` denotes which table members should be considered in the
join: *master* – all master members (left outer join), *detail* – all
detail members (right outer join) and *match* – members must match (inner
join)."""

class Join(Hashable):

    # TODO: [typingI nvestigate optional keys - where, how?
    # Master table (fact in star schema)
    master: JoinKey
    # Detail table (dimension in star schema)
    detail: JoinKey
    # Optional alias for the detail table
    alias: Optional[str]
    # Method how the table is joined
    method: JoinMethod

    def __init__(self,
            master: JoinKey,
            detail: JoinKey,
            alias: Optional[str]=None,
            method: Optional[JoinMethod]=None) -> None: 
        self.master = master
        self.detail = detail
        self.alias = alias
        self.method = method or JoinMethod.match


    def __hash__(self) -> int:
        return hash(self.master) ^ hash(self.detail) \
                ^ hash(self.alias) ^ hash(self.method)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Join):
            return False
        else:
            return self.master == other.master \
                    and self.detail == other.detail \
                    and self.alias == other.alias \
                    and self.method == other.method

    @classmethod
    def from_dict(cls, obj: JSONType) -> "Join":
        """Create `Join` tuple from a JSON dictionary with keys:

        * ``master`` – master table and key specification (see `JoinKey`)
        * ``detail`` - detail table and key specification (see `JoinKey`)
        * ``alias`` – optional alias for the joined clause
        * ``method`` – join method

        Alternative JSON structure is accepted: a list [`master`, `detail`,
        `alias`, `method`]. This is deprecated and will be removed.
        """
        master: JoinKey
        detail: JoinKey
        alias: Optional[str]
        method_name: Optional[str]
        method: JoinMethod

        # TODO: Deprecated, remove
        if isinstance(obj, list):
            alias  = None
            method = None

            if len(obj) < 2 or len(obj) > 4:
                raise ArgumentError(f"Join object can have 1 to 4 items"
                                    f" has {len(obj)}: {obj}")

            padded: List[str]
            padded = obj + [None] * (4 - len(obj))

            master = JoinKey.from_dict(obj[0])
            detail = JoinKey.from_dict(obj[1])
            alias = obj[2]
            method_name = obj[3]

        elif isinstance(obj, dict):
            if "master" not in obj:
                raise ArgumentError(f"Join '{obj}' has no master.")
            else: 
                master = JoinKey.from_dict(obj["master"])

            if "detail" not in obj:
                raise ArgumentError(f"Join '{obj}' has no detail.")
            else:
                detail = JoinKey.from_dict(obj["detail"])

            alias = obj.get("alias")
            method_name = obj.get("method")

        else:
            raise ArgumentError(f"Invalid Join specification: '{obj}'")

        if method_name is None:
            method = JoinMethod.match
        else:
            method = JoinMethod[method_name.lower()]  # type: ignore

        return Join(master=master, detail=detail, alias=alias, method=method)


"""Physical column (or column expression) reference. `schema` is a database
schema name, `table` is a table (or table expression) name containing the
`column`. `extract` is an element to be extracted from complex data type such
as date or JSON (in postgres). `function` is name of unary function to be
applied on the `column`.

Note that either `extract` or `function` can be used, not both."""

class ColumnReference(Hashable):
    column: str
    table: Optional[str]
    schema: Optional[str]
    extract: Optional[str]
    function: Optional[str]

    def __init__(self,
            column: str,
            table: Optional[str]=None,
            schema: Optional[str]=None,
            extract: Optional[str]=None,
            function: Optional[str]=None,
            ) -> None:
        self.column = column
        self.table = table
        self.schema = schema
        self.extract = extract
        self.function = function

    def __hash__(self) -> int:
        return hash(self.column) ^ hash(self.table) ^ hash(self.schema) \
                ^ hash(self.extract) ^ hash(self.function)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ColumnReference):
            return False
        else:
            return self.column == other.column \
                    and self.table == other.table \
                    and self.schema == other.schema \
                    and self.extract == other.extract \
                    and self.function == other.function

    @classmethod
    def from_dict(cls, obj: JSONType) -> "ColumnReference":
        """Create a `Column` reference object from a JSON object which can be:

        * string with optional schema and table in format
          ``[[schema.]table.]column``
        * dictionary with keys `schema`, `table`, `column` or `columns`
        """

        if obj is None:
            raise ArgumentError("Mapping object can not be None")

        if isinstance(obj, str):
            split: List[Optional[str]]
            split = obj.split(".")
            if len(split) > 3:
                raise Exception("Join key `{obj}` has too many components.")
            split = [None] * (3 - len(split)) + split

            schema = split[0]
            table = split[1]
            column = split[2]
        # TODO: Deprecated
        elif isinstance(obj, list):
            split = [None] * (3 - len(split)) + split

            schema = split[0]
            table = split[1]
            column = split[2]
        else:
            schema = obj.get("schema")
            table = obj.get("table")
            column = obj.get("column")
            extract = obj.get("extract")
            function = obj.get("function")

        return ColumnReference(
                schema=schema,
                table=table,
                column=column,
                extract=extract,
                function=function)


