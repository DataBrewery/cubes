from .common import decamelize, to_identifier
from collections import defaultdict

_namespaces = defaultdict(dict)

def get_namespace(name):
    """Gets a namespace `name` dictionary."""

    return _namespaces[name]

def initialize_namespace(name, objects=None, root_class=None, suffix=None):
    """Initializes the namespace `name` with `objects` dictionary and
    subclasses of `root_class` where the class name is decamelized, changet do
    an identifier and with `suffix` removed."""

    if root_class:
        base = collect_subclasses(root_class, suffix)
    else:
        base = {}

    if objects:
        base.update(objects)
    _namespaces[name] = base
    return base

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

