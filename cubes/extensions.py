# -*- coding: utf-8 -*-
from .common import decamelize, to_identifier, coalesce_options
from .errors import *
from collections import defaultdict


# Known extension types.
# Keys:
#     base: extension base class name
#     suffix: extension class suffix to be removed for default name (same as
#         base class nameif not specified)
#     modules: a dictionary of extension names and module name to be loaded
#         laily

_default_modules = {
    "store": {
        "sql":"cubes.backends.sql.store",
        "mongo":"cubes.backends.mongo",
        "mixpanel":"cubes.backends.mixpanel.store",
        "slicer":"cubes.backends.slicer.store",
        "ga":"cubes.backends.ga.store",
    },
    "browser": {
        "snowflake":"cubes.backends.sql.browser",
        "snapshot": "cubes.backends.sql.browser",
        "mixpanel":"cubes.backends.mixpanel.browser",
        "slicer":"cubes.backends.slicer.browser",
        "ga":"cubes.backends.ga.browser",
    },
    "model_provider": {
        "mixpanel":"cubes.backends.mixpanel.store",
        "slicer":"cubes.backends.slicer.store",
        "ga":"cubes.backends.ga.store",
    },
    "request_log_handler": {
        "sql":"cubes.backends.sql.logging",
    },
}

_extension_bases = {
    "store": "Store",
    "model_provider": "ModelProvider",
    "browser": "AggregationBrowser",
    "authorizer": "Authorizer",
    "authenticator": "Authenticator",
    "request_log_handler": "RequestLogHandler",
}

_base_modules = {
    "store": "cubes.stores",
    "model_provider": "cubes.providers",
    "browser": "cubes.browser",
    "authorizer": "cubes.auth",
    "authenticator": "cubes.server.auth",
    "request_log_handler": "cubes.server.logging",
    "formatter": "cubes.formatters",
}

class Extensible(object):
    """For now just an extension superclass to find it's subclasses."""

    """Extension type, such as `store` or `browser`. Default is derived
    from the extension root class name."""
    __extension_type__ = None

    """Class name suffix to be stripped to get extension's base name. Default
    is the root class name"""
    __extension_suffix__ = None

    """Extension name, such as `sql`. Default is derived from the extension
    class name."""
    __extension_name__ = None
    __extension_aliases__ = []

    """List of extension options.  The options is a list of dictionaries with
    keys:

    * `name` – option name
    * `type` – option data type (default is ``string``)
    * `description` – description (optional)
    * `label` – human readable label (optional)
    * `values` – valid values for the option.
    """
    __options__ = None

class ExtensionsFactory(object):
    def __init__(self, root):
        """Creates an extension factory for extension root class `root`."""
        self.root = root
        name = root.__name__

        # Get extension collection name, such as 'stores', 'browsers', ...
        self.name = root.__extension_type__
        if not self.name:
            self.name = to_identifier(decamelize(name))

        self.suffix = root.__extension_suffix__
        if not self.suffix:
            self.suffix = name


        self.options = {}
        self.option_types = {}

        self.extensions = {}

        for option in root.__options__ or []:
            name = option["name"]
            self.options[name] = option
            self.option_types[name] = option.get("type", "string")

    def __call__(self, _extension_name, *args, **kwargs):
        return self.create(_extension_name, *args, **kwargs)

    def create(self, _extension_name, *args, **kwargs):
        """Creates an extension. First argument should be extension's name."""
        extension = self.get(_extension_name)

        option_types = dict(self.option_types)
        for option in extension.__options__ or []:
            name = option["name"]
            option_types[name] = option.get("type", "string")

        kwargs = coalesce_options(dict(kwargs), option_types)

        return extension(*args, **kwargs)


    def get(self, name):
        if name in self.extensions:
            return self.extensions[name]

        # Load module...
        modules = _default_modules.get(self.name)
        if modules and name in modules:
            # TODO don't load module twice (once for manager once here)
            _load_module(modules[name])

        self.discover()

        try:
            return self.extensions[name]
        except KeyError:
            raise ConfigurationError("Unknown extension '%s' of type %s"
                                     % (name, self.name))

    def discover(self):
        extensions = collect_subclasses(self.root, self.suffix)
        self.extensions.update(extensions)

        aliases = {}
        for name, ext in extensions.items():
            if ext.__extension_aliases__:
                for alias in ext.__extension_aliases__:
                    aliases[alias] = ext

        self.extensions.update(aliases)


class ExtensionsManager(object):
    def __init__(self):
        self.managers = {}
        self._is_initialized = False

    def __lazy_init__(self):
        for root in Extensible.__subclasses__():
            manager = ExtensionsFactory(root)
            self.managers[manager.name] = manager
        self._is_initialized = True

    def __getattr__(self, type_):
        if not self._is_initialized:
            self.__lazy_init__()

        if type_ in self.managers:
            return self.managers[type_]

        # Retry with loading the required base module

        _load_module(_base_modules[type_])
        self.__lazy_init__()

        try:
            return self.managers[type_]
        except KeyError:
            raise InternalError("Unknown extension type '%s'" % type_)

"""Extensions provider. Use::

    browser = extensions.browser("sql", ...)

"""
extensions = ExtensionsManager()


def collect_subclasses(parent, suffix=None):
    """Collect all subclasses of `parent` and return a dictionary where keys
    are object names. Obect name is decamelized class names transformed to
    identifiers and with `suffix` removed. If a class has class attribute
    `__identifier__` then the attribute is used as name."""

    subclasses = {}
    for c in subclass_iterator(parent):
        name = None
        if hasattr(c, "__extension_name__"):
            name = getattr(c, "__extension_name__")
        elif hasattr(c, "__identifier__"):
            # TODO: depreciated
            name = getattr(c, "__identifier__")

        if not name:
            name = c.__name__
            if suffix and name.endswith(suffix):
                name = name[:-len(suffix)]
            name = to_identifier(decamelize(name))

        subclasses[name] = c

    return subclasses


def subclass_iterator(cls, _seen=None):
    """
    Generator over all subclasses of a given class, in depth first order.

    Source: http://code.activestate.com/recipes/576949-find-all-subclasses-of-a-given-class/
    """

    if not isinstance(cls, type):
        raise TypeError('_subclass_iterator must be called with '
                        'new-style classes, not %.100r' % cls)

    _seen = _seen or set()

    try:
        subs = cls.__subclasses__()
    except TypeError: # fails only when cls is type
        subs = cls.__subclasses__(cls)
    for sub in subs:
        if sub not in _seen:
            _seen.add(sub)
            yield sub
            for sub in subclass_iterator(sub, _seen):
                yield sub

def _load_module(modulepath):
    mod = __import__(modulepath)
    path = []
    for token in modulepath.split(".")[1:]:
       path.append(token)
       mod = getattr(mod, token)
    return mod
