# -*- coding: utf-8 -*-

from typing import (
        Any,
        cast,
        Collection,
        Dict,
        List,
        Optional,
        Type,
        TypeVar,
        Union,
    )

from collections import OrderedDict
from textwrap import dedent
from pkg_resources import iter_entry_points

from .common import decamelize, coalesce_options
from .errors import ArgumentError, InternalError, ConfigurationError

from importlib import import_module

__all__ = [
    "EXTENSION_TYPES",
    "ExtensionFinder",
]

# Known extension types.
# Keys:
#     base: extension base class name
#     suffix: extension class suffix to be removed for default name (same as
#         base class nameif not specified)
#     modules: a dictionary of extension names and module name to be loaded
#         laily

BUILTIN_EXTENSION_MODULES = {
    "authenticator": {
        "admin_admin": "cubes.server.auth",
        "pass_parameter": "cubes.server.auth",
        "http_basic_proxy": "cubes.server.auth",
    },
    "authorizer": {
        "simple": "cubes.auth",
    },
    "browser": {
        "sql":"cubes.sql.browser",
        "slicer":"cubes.server.browser",
    },
    "formatter": {
        "cross_table": "cubes.formatters",
        "csv": "cubes.formatters",
        'xlsx': 'cubes.formatters',
        "html_cross_table": "cubes.formatters",
    },
    "model_provider": {
        "default":"cubes.metadata.providers",
        "slicer":"cubes.server.store",
    },
    "request_log_handler": {
        "default": "cubes.server.logging",
        "csv": "cubes.server.logging",
        'xlsx': 'cubes.server.logging',
        "json": "cubes.server.logging",
        "sql": "cubes.sql.logging",
    },
    "store": {
        "sql":"cubes.sql.store",
        "slicer":"cubes.server.store",
    },
}

EXTENSION_TYPES = {
    "browser": "Aggregation browser",
    "store": "Data store",
    "model_provider": "Model provider",
    "formatter": "Formatter",
    "authorizer": "Authorizer",
    "authenticator": "Authenticator",
    "request_log_handler": "Request log handler",
}

from enum import Enum

from .errors import ArgumentError

TRUE_VALUES = ["1", "true", "yes"]
FALSE_VALUES = ["0", "false", "no"]


class Parameter:
    name: str
    default: Any
    type: str
    desc: Optional[str]
    label: str
    values: Collection[str]

    def __init__(self,
            name: str,
            type_: Optional[str]=None,
            default: Optional[Any]=None,
            desc: Optional[str]=None,
            label: Optional[str]=None,
            values: Optional[Collection[str]]=None) -> None:
        self.name = name
        self.default = default
        self.type = type_ or "string"
        self.desc = desc
        self.label = label or name
        self.values = values or []

    def coalesce_value(self, value: Any) -> Any:
        """ Convert string into an object value of `value_type`. The type might
        be: `string` (no conversion), `integer`, `float`
        """

        return_value: Any

        try:
            if self.type == "string":
                return_value = str(value)
            elif self.type == "float":
                return_value = float(value)
            elif self.type == "integer":
                return_value = int(value)
            elif self.type == "bool":
                if not value:
                    return_value = False
                elif isinstance(value, str):
                    return_value = value.lower() in TRUE_VALUES
                else:
                    return_value = bool(value)
            else:
                raise ConfigurationError(f"Unknown option value type {self.type}")

        except ValueError:
            label: str

            if self.label:
                label = f"parameter {self.label} "
            else:
                label = f"parameter {self.name} "

            raise ConfigurationError(f"Unable to convert {label} value '{value}' "
                                     f"into type {self.type}")

        return return_value


T = TypeVar('T', bound=Type["Extensible"])
import inspect

# TODO: Lazy extensions [name, module]

class ExtensionRegistry:
    classes: Dict[str, Dict[str, Type["Extensible"]]]

    def __init__(self) -> None:
        self.classes = {}
        for type_ in EXTENSION_TYPES.keys():
            self.classes[type_] = {}

    def register_extension(cls,
            type_: str,
            name: str,
            extension: Type["Extensible"]) -> None:
        if type_ == "undefined":
            raise InternalError(f"Extension '{extension}' has no concrete "
                                f"Extensible subclass as it's superclass.")
        if type_ not in EXTENSION_TYPES:
            raise InternalError(f"Unsupported extension type '{type_}'")

        cls.classes[type_][name] = extension

    def _register_builtin(self, type_: str, name: str) -> None:
        if type_ in BUILTIN_EXTENSION_MODULES:
            ext_modules = BUILTIN_EXTENSION_MODULES[type_]
            if name in ext_modules:
                import_module(ext_modules[name])

    def get_extension(self, type_: str, name: str) -> Type["Extensible"]:
        ext_class: Type["Extensible"]
        registry = self.classes[type_]

        if not name in registry:
            self._register_builtin(type_, name)

        try:
            ext_class = registry[name]
        except KeyError:
            raise InternalError(f"Unknown extension '{name}' of type '{type_}'")

        return ext_class


class Extensible:
    __extension_type__ = "undefined"
    __registry__: ExtensionRegistry = ExtensionRegistry()
    __parameters__: List[Parameter] = []

    def __init_subclass__(cls, name: Optional[str]=None, abstract: bool=False) -> None:
        if name is not None and abstract \
                or name is None and not abstract:
            raise InternalError(
               f"Extension class {cls} should have either name "
               f"or abstract flag specified.")

        if name is not None:
            cls.__registry__.register_extension(cls.__extension_type__,
                                                name, cls)
        else:
            if cls.__extension_type__ == "undefined":
                raise InternalError(f"Abstract extension '{cls}' has no "
                                    f"concrete __extension_type__ "
                                    f"assigned")

    @classmethod
    def concrete_extension(cls: T, name: str) -> Type[T]:
        ext: Type["Extensible"]
        ext = cls.__registry__.get_extension(cls.__extension_type__, name)
        return cast(Type[T], ext)

    @classmethod
    def create_with_params(cls: T, params: Dict[str, Any]) -> T:
        kwargs: Dict[str, Any]
        kwargs = {}

        for param in cls.__parameters__:
            if param.name in params: 
                value = params[param.name]
                kwargs[param.name] = param.coalesce_value(value)
            elif param.default:
                value = param.default
                kwargs[param.name] = param.coalesce_value(value)
            else:
                typename = cls.__extension_type__
                raise ConfigurationError(f"Invalid parameter '{param.name}' "
                                         f"for extension: {typename}")

        return cast(T, cls(**kwargs))  # type: ignore

