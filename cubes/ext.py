# -*- coding: utf-8 -*-

from typing import (
        Any,
        cast,
        Collection,
        Dict,
        List,
        NamedTuple,
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

BUILTIN_EXTENSION_MODULES: Dict[str, Dict[str, str]]
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

EXTENSION_TYPES: Dict[str, str] = {
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


class ExtensionDescription(NamedTuple):
    type: str
    name: str
    label: str
    doc: str
    params: List[Parameter]


class ExtensionRegistry:
    name: str
    classes: Dict[str, Type["Extensible"]]
    modules: Dict[str, str]

    def __init__(self, name: str) -> None:
        self.name = name
        self.classes = {}
        self.modules = {}

    def register_extension(self, name: str, extension: Type["Extensible"]) \
            -> None:

        # Sanity assertion. Should not happen, but still...
        assert(issubclass(extension, Extensible))

        self.classes[name] = extension

    def register_lazy_extension(self, name: str, module: str) -> None:
        """Register extension `name` which exists in module `module`"""
        self.modules[name] = module

    def extension(self, name: str) -> Type["Extensible"]:
        extension: Type[Extensible]

        if name not in self.classes and name in self.modules:
            # Try to load module
            import_module(self.modules[name])

        try:
            extension = self.classes[name]
        except KeyError:
            raise InternalError(f"Unknown extension '{name}' "
                                f"of type '{self.name}'")

        return extension

    def names(self) -> Collection[str]:
        """Return extension `type_` names"""
        names: List[str]
        names = list(set(self.classes.keys()) | set(self.modules.keys()))
        return sorted(names)

    def describe(self, name: str) -> ExtensionDescription:
        ext = self.extension(name)
        desc = ExtensionDescription(
                type= self.name,
                name= name,
                label= name,
                doc= ext.__doc__ or "(no documentation)",
                params = ext.__parameters__ or [])

        return desc


_registries: Dict[str, ExtensionRegistry] = {}

def _initialize_registry(name: str) -> None:
    assert name not in _registries, \
           f"Extension registry '{name}' already initialized"

    registry = ExtensionRegistry(name)

    modules: Dict[str, str]
    modules = BUILTIN_EXTENSION_MODULES.get(name, {})
    for ext, module in modules.items():
        registry.register_lazy_extension(ext, module)

    _registries[name] = registry


def get_registry(name: str) -> ExtensionRegistry:
    """Get extension registry for extensions of type `name`."""
    global _registries

    if name not in EXTENSION_TYPES:
        raise InternalError(f"Unknown extension type '{name}'")

    if name not in _registries:
        _initialize_registry(name)

    return _registries[name]


class Extensible:
    __extension_type__ = "undefined"
    __parameters__: List[Parameter] = []

    def __init_subclass__(cls, name: Optional[str]=None, abstract: bool=False) -> None:
        assert cls.__extension_type__ in EXTENSION_TYPES, \
               f"Invalid extension type '{cls.__extension_type__}' " \
               f"for extension '{cls}'"

        # Note: We reqire either name or a flag explicitly to prevent potential
        # hidden errors by accidentally omitting the extension name.
        assert (name is not None) ^ abstract, \
               f"Extension class {cls} should have either name " \
               f"or abstract flag specified."

        if name is not None:
            registry: ExtensionRegistry
            registry = get_registry(cls.__extension_type__)
            registry.register_extension(name, cls)
        else:
            if cls.__extension_type__ == "undefined":
                raise InternalError(f"Abstract extension '{cls}' has no "
                                    f"concrete __extension_type__ "
                                    f"assigned")
            else:
                # We do nothing for abstract subclasses
                pass

    @classmethod
    def concrete_extension(cls: T, name: str) -> Type[T]:
        registry: ExtensionRegistry
        registry = get_registry(cls.__extension_type__)
        return cast(Type[T], registry.extension(name))

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

