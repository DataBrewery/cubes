from typing import Dict, Any, Tuple, Optional

# Types

JSONType = Dict[str, Any]
OptionsType = Dict[str, str]

# Used in Workspace
# TODO: Should be namedtuple: ref, identity, locale

_CubeKey = Tuple[str, Any, Optional[str]]

