# -*- coding: utf-8 -*-

from typing import (
        Any,
        cast,
        Collection,
        Dict,
        List,
        Mapping,
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
from .settings import Setting, SettingsDict

from importlib import import_module

T = TypeVar('T', bound=Type["Extensible"])

__all__ = [
    "Extensible",
    "ExtensionRegistry",
    "get_registry",
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


class ExtensionDescription(NamedTuple):
    type: str
    name: str
    label: str
    doc: str
    settings: List[Setting]


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
        doc: str
        doc = ext.extension_desc or ext.__doc__ or "(No documentation)"

        desc = ExtensionDescription(
                type= self.name,
                name= name,
                label= ext.extension_label or name,
                doc=doc,
                settings = ext.extension_settings or [])

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
    extension_settings: List[Setting] = []
    extension_desc: Optional[str] = None
    extension_label: Optional[str] = None

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
    def create_with_dict(cls: T, mapping: Mapping[str, Any]) -> T:
        settings: SettingsDict
        settings = SettingsDict(mapping=mapping, settings=cls.extension_settings)

        return cls.create_with_settings(settings)

    @classmethod
    def create_with_settings(cls: T, settings: SettingsDict) -> T:
        return cast(T, cls(**SettingsDict))  # type: ignore

