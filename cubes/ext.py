# -*- coding: utf-8 -*-
from collections import OrderedDict
from textwrap import dedent
from pkg_resources import iter_entry_points

from .common import decamelize, coalesce_options
from .errors import ArgumentError, InternalError, BackendError


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


EXTENSION_TYPES = {
    "browser": "Aggregation browser",
    "store": "Data store",
    "model_provider": "Model provider",
    "formatter": "Formatter",
    "authorizer": "Authorizer",
    "authenticator": "Authenticator",
    "request_log_handler": "Request log handler",
}

# Information about built-in extensions. Supposedly faster loading (?).
#
_BUILTIN_EXTENSIONS = {
    "authenticators": {
        "admin_admin": "cubes.server.auth:AdminAdminAuthenticator",
        "pass_parameter": "cubes.server.auth:PassParameterAuthenticator",
        "http_basic_proxy": "cubes.server.auth:HTTPBasicProxyAuthenticator",
    },
    "authorizers": {
        "simple": "cubes.auth:SimpleAuthorizer",
    },
    "browsers": {
        "sql":"cubes.sql.browser:SQLBrowser",
        "slicer":"cubes.server.browser:SlicerBrowser",
    },
    "formatters": {
        "cross_table": "cubes.formatters:CrossTableFormatter",
        "csv": "cubes.formatters:CSVFormatter",
        "html_cross_table": "cubes.formatters:HTMLCrossTableFormatter",
    },
    "providers": {
        "default":"cubes.providers:StaticModelProvider",
        "slicer":"cubes.server.store:SlicerModelProvider",
    },
    "request_log_handlers": {
        "default":"cubes.server.logging:DefaultRequestLogHandler",
        "csv":"cubes.server.logging:CSVFileRequestLogHandler",
        "json":"cubes.server.logging:JSONRequestLogHandler",
        "sql":"cubes.sql.logging:SQLRequestLogger",
    },
    "stores": {
        "sql":"cubes.sql.store:SQLStore",
        "slicer":"cubes.server.store:SlicerStore",
    },
}

_DEFAULT_OPTIONS = {
}

class _Extension(object):
    """
    Cubes Extension wrapper.

    `options` – List of extension options.  The options is a list of
    dictionaries with keys:

    * `name` – option name
    * `type` – option data type (default is ``string``)
    * `description` – description (optional)
    * `label` – human readable label (optional)
    * `values` – valid values for the option.
    """
    def __init__(self, type_, entry=None, factory=None, name=None):
        if factory is not None and entry is not None:
            raise ArgumentError("Can't set both extension factory and entry "
                                "(in extension '{}')".format(name))

        elif factory is None and entry is None:
            raise ArgumentError("Neither extension factory nor entry provided "
                                "(in extension '{}')".format(name))

        self.type_ = type_
        self.entry = entry
        self.name = name or entry.name

        # After loading...
        self.options = []
        self.option_types = {}
        self._factory = None

        if factory is not None:
            self.factory = factory

    @property
    def factory(self):
        if self._factory is not None:
            return self._factory
        elif self.entry:
            # This must not fail or result in None
            self.factory = self.entry.load()
            return self._factory
        else:
            raise InternalError("No factory or entry set for extension '{}'"
                                .format(self.name))

    @factory.setter
    def factory(self, factory):
        if factory is None:
            raise InternalError("Can't set extension factory to None")

        self._factory = factory
        defaults = _DEFAULT_OPTIONS.get(self.type_, [])

        if hasattr(self._factory, "__options__"):
            options = self._factory.__options__ or []
        else:
            options = []

        self.options = OrderedDict()
        for option in defaults + options:
            name = option["name"]
            self.options[name] = option
            self.option_types[name] = option.get("type", "string")

        self.option_types = self.option_types or {}

    @property
    def is_builtin(self):
        return self.entry is None

    @property
    def label(self):
        if hasattr(self.factory, "__label__"):
            return self.factory.__label__
        else:
            return decamelize(self.factory.__name__)

    @property
    def description(self):
        if hasattr(self.factory, "__description__"):
            desc = self.factory.__description__ or ""
            return dedent(desc)
        else:
            return ""

    def create(self, *args, **kwargs):
        """Creates an extension. First argument should be extension's name."""
        factory = self.factory

        kwargs = coalesce_options(dict(kwargs),
                                  self.option_types)

        return factory(*args, **kwargs)


class ExtensionFinder(object):
    def __init__(self, type_):
        self.type_ = type_
        self.group = "cubes.{}".format(type_)
        self.extensions = {}

        self.builtins = _BUILTIN_EXTENSIONS.get(self.type_, {})

    def discover(self, name=None):
        """Find all entry points."""
        for obj in iter_entry_points(group=self.group, name=name):
            ext = _Extension(self.type_, obj)
            self.extensions[ext.name] = ext

    def builtin(self, name):
        try:
            ext_mod = self.builtins[name]
        except KeyError:
            return None

        (modname, attr) = ext_mod.split(":")
        module = _load_module(modname)
        factory = getattr(module, attr)
        ext = _Extension(self.type_, name=name, factory=factory)
        self.extensions[name] = ext

        return ext

    def names(self):
        """Return list of extension names."""
        if not self.extensions:
            self.discover()

        names = list(self.builtins.keys())
        names += self.extensions.keys()

        return sorted(names)

    def get(self, name):
        """Return extenson object by name. Load if necessary."""
        ext = self.extensions.get(name)

        if not ext:
            ext = self.builtin(name)

        if not ext:
            self.discover()

            try:
                ext = self.extensions[name]
            except KeyError:
                raise InternalError("Unknown '{}' extension '{}'"
                                    .format(self.type_, name))
        return ext

    def __call__(self, _ext_name, *args, **kwargs):
        return self.create(_ext_name, *args, **kwargs)

    def factory(self, name):
        """Return extension factory."""
        ext = self.get(name)

        if not ext.factory:
            raise BackendError("Unable to get factory for extension '{}'"
                               .format(name))

        return ext.factory

    def create(self, _ext_name, *args, **kwargs):
        """Create an instance of extension `_ext_name` with given arguments.
        The keyword arguments are converted to their appropriate types
        according to extensions `__options__` list. This allows options to be
        specified as strings in a configuration files or configuration
        variables."""
        ext = self.get(_ext_name)
        return ext.create(*args, **kwargs)

    def register(self, _ext_name, factory):
        ext = _Extension(self.type_, name=_ext_name)
        ext.factory = factory
        self.extensions["name"] = ext

        return ext


def _load_module(modulepath):
    """Load module `modulepath` and return the last module object in the
    module path."""

    mod = __import__(modulepath)
    path = []
    for token in modulepath.split(".")[1:]:
        path.append(token)
        mod = getattr(mod, token)
    return mod


authenticator = ExtensionFinder("authenticators")
authorizer = ExtensionFinder("authorizers")
browser = ExtensionFinder("browsers")
formatter = ExtensionFinder("formatters")
model_provider = ExtensionFinder("providers")
request_log_handler = ExtensionFinder("request_log_handlers")
store = ExtensionFinder("stores")
