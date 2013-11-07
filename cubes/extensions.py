# -*- coding=utf -*-
from .common import decamelize, to_identifier, coalesce_options
from collections import defaultdict

_default_modules = {
    "stores": {
        "sql":"cubes.backends.sql.store",
        "mongo":"cubes.backends.mongo",
        "mongo2":"cubes.backends.mongo2",
        "mixpanel":"cubes.backends.mixpanel.store",
        "slicer":"cubes.backends.slicer.store",
    },
    "browsers": {
        "snowflake":"cubes.backends.sql.browser",
        "snapshot": "cubes.backends.sql.browser",
        "mixpanel":"cubes.backends.mixpanel.browser",
        "slicer":"cubes.backends.slicer.browser",
    },
    "model_providers": {
        "mixpanel":"cubes.backends.mixpanel.store",
        "slicer":"cubes.backends.slicer.store",
    },
    "query_log_handlers": {
        "sql":"cubes.backends.sql.logging",
    },
    "authorizers": {
    }
}

class Namespace(dict):
    def __init__(self, name, objects=None, root_class=None, suffix=None,
                 option_checking=False):
        self.name = name
        self.root_class = root_class
        self.suffix = suffix
        self.option_checking = option_checking

        if objects:
            self.update(objects)

    def discover_objects(self):
        if self.root_class:
            objects = collect_subclasses(self.root_class, self.suffix)

            if self.option_checking:
                # Convert classes to factories
                for name, class_ in objects.items():
                    objects[name] = _FactoryOptionChecker(class_)

            self.update(objects)

    def __getattr__(self, value):
        return self.__getitem__(value)

    def __getitem__(self, value):
        try:
            return super(Namespace, self).__getitem__(value)
        except KeyError:
            # Lazily load module that might contain the object
            modules = _default_modules.get(self.name)
            if modules and value in modules:
                _load_module(modules[value])
                self.discover_objects()

            # Retry after loading
            return super(Namespace, self).__getitem__(value)

class _FactoryOptionChecker(object):
    def __init__(self, class_, options=None):
        """Creates a factory wrapper for `class_`. Calling the object createds
        an instance of `class_` and configures it according to `options`. If
        not options are specified, then the class variable `__options__` is used.

        The options is a list of dictionaries with keys:

        * `name` – option name
        * `type` – option data type
        * `description` – description (optional)
        * `label` – human readable label (optional)
        * `values` – valid values for the option."""

        if not options and hasattr(class_, "__options__"):
            options = class_.__options__

        self.options = {}
        self.option_types = {}
        for option in options or []:
            name = option["name"]
            self.options[name] = option
            self.option_types[name] = option.get("type", "string")

        self.class_ = class_

    def __call__(self, *args, **kwargs):
        # TODO: move this to a metaclass
        options = dict(kwargs)
        options = coalesce_options(dict(kwargs), self.option_types)

        return self.class_(*args, **options)

_namespaces = {}

def get_namespace(name):
    """Gets a namespace `name` dictionary."""

    return _namespaces.get(name)

def initialize_namespace(name, objects=None, root_class=None, suffix=None,
                         option_checking=False):
    """Initializes the namespace `name` with `objects` dictionary and
    subclasses of `root_class` where the class name is decamelized, changet do
    an identifier and with `suffix` removed."""

    ns = Namespace(name, objects, root_class, suffix,
                   option_checking=option_checking)
    ns.discover_objects()
    _namespaces[name] = ns

    return ns

def collect_subclasses(parent, suffix=None):
    """Collect all subclasses of `parent` and return a dictionary where keys
    are object names. Obect name is decamelized class names transformed to
    identifiers and with `suffix` removed. If a class has class attribute
    `__identifier__` then the attribute is used as name."""

    subclasses = {}
    for c in subclass_iterator(parent):
        if hasattr(c, "__identifier__"):
            name = getattr(c, "__identifier__")
        else:
            name = to_identifier(decamelize(c.__name__))

        if suffix and name.endswith(suffix):
            name = name[:-len(suffix)]
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
