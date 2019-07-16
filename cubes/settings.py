from collections import OrderedDict
from enum import Enum
from typing import Any, Collection, Dict, Iterator, Mapping, Optional, Set, Union

from .errors import ConfigurationError, InternalError

SettingValue = Union[str, float, bool, int]


class SettingType(Enum):
    str = 0
    int = 1
    bool = 2
    float = 3
    store = 4


STRING_SETTING_TYPES = [SettingType.str, SettingType.store]


class Setting:
    name: str
    default: SettingValue
    type: SettingType
    desc: Optional[str]
    label: str
    is_required: bool
    values: Collection[str]

    def __init__(
        self,
        name: str,
        type: Optional[SettingType] = None,
        default: Optional[Any] = None,
        desc: Optional[str] = None,
        label: Optional[str] = None,
        is_required: bool = False,
        values: Optional[Collection[str]] = None,
    ) -> None:
        self.name = name
        self.default = default
        self.type = type or SettingType.str
        self.desc = desc
        self.label = label or name
        self.is_required = is_required
        self.values = values or []


TRUE_VALUES = ["1", "true", "yes", "on"]
FALSE_VALUES = ["0", "false", "no", "off"]


def _to_bool(value: Optional[SettingValue]) -> Optional[bool]:
    retval: Optional[bool]

    if value is None:
        retval = None
    else:
        if isinstance(value, bool):
            retval = value
        elif isinstance(value, (int, float)):
            retval = bool(value)
        elif isinstance(value, str):
            if value in TRUE_VALUES:
                retval = True
            elif value in FALSE_VALUES:
                retval = False
            else:
                raise ValueError
        else:
            raise ValueError

    return retval


def _to_int(value: Optional[SettingValue]) -> Optional[int]:
    retval: Optional[int]

    if value is None:
        retval = None
    else:
        if isinstance(value, bool):
            retval = 1 if value else 0
        elif isinstance(value, int):
            retval = value
        elif isinstance(value, (str, float)):
            retval = int(value)
        else:
            raise ValueError(value)

    return retval


def _to_float(value: Optional[SettingValue]) -> Optional[float]:
    retval: Optional[float]

    if value is None:
        retval = None
    else:
        if isinstance(value, bool):
            retval = 1.0 if value else 0.0
        elif isinstance(value, int):
            retval = float(value)
        elif isinstance(value, float):
            retval = value
        elif isinstance(value, str):
            return float(value)
        else:
            raise ValueError

    return retval


def _to_string(value: Optional[SettingValue]) -> Optional[str]:
    retval: Optional[str]

    if value is None:
        retval = None
    else:
        if isinstance(value, bool):
            retval = "true" if value else "false"
        elif isinstance(value, (str, int, float)):
            retval = str(value)
        else:
            raise ValueError

    return retval


def _cast_value(value: Any, setting: Setting) -> Optional[SettingValue]:
    retval: Optional[SettingValue]

    if setting.type == SettingType.str:
        retval = _to_string(value)
    elif setting.type == SettingType.int:
        retval = _to_int(value)
    elif setting.type == SettingType.float:
        retval = _to_float(value)
    elif setting.type == SettingType.bool:
        retval = _to_bool(value)
    else:
        raise InternalError(f"Unknown setting value type {setting.type}")

    return retval


def distill_settings(
    mapping: Mapping[str, Any],
    settings: Collection[Setting],
    owner: Optional[str] = None,
) -> Dict[str, Optional[SettingValue]]:
    """Coalesce values of `mapping` to match type in `settings`. If the mapping
    contains key that don't have corresponding settings or when the mapping
    does not contain key for a required setting an `ConfigurationError`
    exeption is raised.

    The returned dictionary can be safely used to be passed into an
    extension's `__init__()` method as key-word arguments.
    """

    value: Optional[SettingValue]
    lower_map: Dict[str, Optional[SettingValue]] = {}
    ownerstr: str = f" ({owner})" if owner is not None else ""

    for key, value in mapping.items():
        lower_map[key.lower()] = value

    result: Dict[str, Optional[SettingValue]]
    result = {}

    for setting in settings:
        name: str = setting.name.lower()

        if name in lower_map:
            result[setting.name] = _cast_value(lower_map[name], setting)
        elif setting.is_required:
            raise ConfigurationError(f"Setting '{name}'{ownerstr}" f" is required")
        elif setting.default is not None:
            # We assume that extension developers provide values in correct
            # type
            result[name] = setting.default

    keys: Set[str]
    keys = set(mapping.keys()) - {s.name for s in settings}
    if keys:
        alist: str = ", ".join(sorted(keys))
        raise ConfigurationError(f"Unknown settings{ownerstr}: {alist}")

    return result


# Note: This is a little similar to the ConfigParser section mapping, but
# richer information
#
class SettingsDict(Mapping[str, Optional[SettingValue]]):
    """Case-insensitive lookup of typed values."""

    _dict: Dict[str, Optional[SettingValue]]
    _settings: Dict[str, Setting]

    def __init__(
        self, mapping: Mapping[str, SettingValue], settings: Collection[Setting]
    ) -> None:
        """Create a dictionary of settings from `mapping`.

        Only items specified in the `settings` are going to be included
        in the new settings dictionary.
        """

        self._dict = distill_settings(mapping, settings)
        self._settings = OrderedDict((s.name, s) for s in settings)

    def __getitem__(self, key: str) -> Any:
        return self._dict[key]

    def __len__(self) -> int:
        return len(self._dict)

    def __iter__(self) -> Iterator[str]:
        return iter(self._dict.keys())
