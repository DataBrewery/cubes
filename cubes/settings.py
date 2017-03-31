from typing import (
        Any,
        Collection,
        Dict,
        Mapping,
        NamedTuple,
        Iterator,
        Optional,
        Union,
        Tuple,
        cast,
    )

import collections.abc as abc
from collections import OrderedDict
from .errors import InternalError, ConfigurationError


SettingValue = Union[str, float, bool, int]

class Setting:
    name: str
    default: SettingValue
    type: str
    desc: Optional[str]
    label: str
    is_require: bool
    values: Collection[str]

    def __init__(self,
            name: str,
            type: Optional[str]=None,
            default: Optional[Any]=None,
            desc: Optional[str]=None,
            label: Optional[str]=None,
            is_required: bool=False,
            values: Optional[Collection[str]]=None) -> None:
        self.name = name
        self.default = default
        self.type = type or "string"
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

# Note: This is a little similar to the ConfigParser section mapping, but
# richer information
#
class SettingsDict(Mapping[str, Optional[SettingValue]]):
    """Case-insensitive lookup of typed values."""

    _dict: Dict[str, Optional[SettingValue]]
    _settings: Dict[str, Setting]

    def __init__(self,
                mapping: Mapping[str, SettingValue],
                settings: Collection[Setting],
            ) -> None:
        """Create a dictionary of settings from `mapping`. Only items specified
        in the `settings` are going to be included in the new settings
        dictionary."""

        lower_map: Dict[str, Optional[SettingValue]] = {}
        for key, value in mapping.items():
            lower_map[key.lower()] = value

        self._dict = {}
        self._settings = OrderedDict()

        for setting in settings:
            name: str
            name = setting.name.lower()
            if name in lower_map:
                self._dict[name] = lower_map[name]
            elif setting.is_required:
                raise ConfigurationError(f"Setting '{name}' ('{setting.label}')"
                                         f" is required")
            else:
                self._dict[name] = setting.default

            self._settings[name] = setting

        keys: Set[str]
        keys = set(mapping.keys()) - set(s.name for s in settings)
        if keys:
            alist: str = ", ".join(sorted(keys))
            raise ConfigurationError(f"Unknown settings: {alist}")

    def _invalid_value(self, key: str, value: SettingValue) -> Exception:
        raise ValueError(f"Invalid value type '{type(value)}' for "
                         f"setting {self._settings[key].name}")

    def get_value(self, key: str) -> Optional[SettingValue]:
        """ Convert string into an object value of `value_type`. The type might
        be: `string` (no conversion), `integer`, `float`
        """
        retval: Optional[SettingValue]

        lkey: str = key.lower()

        if lkey not in self._dict:
            raise KeyError(key)

        value: Optional[SettingValue]
        value = self._dict.get(lkey)

        setting = self._settings[lkey]

        if setting.type == "string":
            retval = _to_string(value)
        elif setting.type == "integer":
            retval = _to_int(value)
        elif setting.type == "float":
            retval = _to_float(value)
        elif setting.type == "boolean":
            retval = _to_bool(value)
        else:
            raise InternalError(f"Unknown setting value type {setting.type}")
        
        return retval

    def __getitem__(self, key: str) -> Any:
        return self.get_value(key)

    def __len__(self) -> int:
        return len(self._dict)

    def __iter__(self) -> Iterator[str]:
        return iter(self._dict.keys())
