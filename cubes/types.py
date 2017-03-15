from typing import (
        Any,
        Dict,
        Mapping,
        Optional,
        Tuple,
    )

# Type used as a placeholder during type annotation process. There should be no
# values of this type in the future. Used to mark:
#
# - Type that was not yet determined with satisfaction
# - Type that needs to be redesigned
#
_UnknownType = Any


# Various Type Aliases
# --------------------
JSONType = Dict[str, Any]
OptionsType = Dict[str, str]

# Used in Workspace
# TODO: Should be namedtuple: ref, identity, locale

_CubeKey = Tuple[str, Any, Optional[str]]

# TODO: [typing] See #410
_RecordType = Mapping[str, Any]
