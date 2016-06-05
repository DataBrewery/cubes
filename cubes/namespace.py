# -*- coding: utf-8 -*-

from __future__ import absolute_import

from .errors import NoSuchCubeError, NoSuchDimensionError, ModelError
from .common import read_json_file
from . import compat

__all__ = [
    "Namespace",
]

class Namespace(object):
    def __init__(self, name=None, parent=None):
        """Creates a cubes namespace – an object that provides model objects
        from the providers."""
        # TODO: Assign this on __init__, namespaces should not be freely
        # floating until anchored in another namespace
        self.parent = parent
        self.name = name
        self.namespaces = {}
        self.providers = []
        self.translations = {}

    def namespace(self, path, create=False):
        """Returns a tuple (`namespace`, `remainder`) where `namespace` is
        the deepest namespace in the namespace hierarchy and `remainder` is
        the remaining part of the path that has no namespace (is an object
        name or contains part of external namespace).

        If path is empty or not provided then returns self.

        If `create` is `True` then the deepest namespace is created if it does
        not exist.
        """

        if not path:
            return (self, None)

        if isinstance(path, compat.string_type):
            path = path.split(".")

        namespace = self
        for i, element in enumerate(path):
            remainder = path[i+1:]
            if element in namespace.namespaces:
                namespace = namespace.namespaces[element]
                found = True
            else:
                remainder = path[i:]
                break

        if not create:
            return (namespace, ".".join(remainder) or None)
        else:
            for element in remainder:
                namespace = namespace.create_namespace(element)

            return (namespace, None)

    def create_namespace(self, name):
        """Create a namespace `name` in the receiver."""
        if self.name:
            nsname = "%s.%s" % (self.name, name)
        else:
            nsname = name

        namespace = Namespace(nsname, parent=self)
        self.namespaces[name] = namespace

        return namespace

    def find_cube(self, cube_ref):
        """Returns a tuple (`namespace`, `provider`, `basename`) where
        `namespace` is a namespace conaining `cube`, `provider` providers the
        model for the cube and `basename` is a name of the `cube` within the
        `namespace`. For example: if cube is ``slicer.nested.cube`` and there
        is namespace ``slicer`` then that namespace is returned and the
        `basename` will be ``nested.cube``.

        Raises `NoSuchCubeError` when there is no cube with given reference.
        """

        cube_ref = str(cube_ref)
        split = cube_ref.split(".")
        if len(split) > 1:
            path = split[0:-1]
            cube_ref = split[-1]
        else:
            path = []
            cube_ref = cube_ref

        (namespace, remainder) = self.namespace(path)

        if remainder:
            basename = "{}.{}".format(remainder, cube_ref)
        else:
            basename = cube_ref

        # Find first provider that knows about the cube `name`
        provider = None

        for provider in namespace.providers:
            if provider.has_cube(cube_ref):
                break
        else:
            provider = None

        if not provider:
            raise NoSuchCubeError("Unknown cube '{}'".format(cube_ref),
                                  cube_ref)

        return (namespace, provider, basename)


    def list_cubes(self, recursive=False):
        """Retursn a list of cube info dictionaries with keys: `name`,
        `label`, `description`, `category` and `info`."""

        all_cubes = []
        cube_names = set()
        for provider in self.providers:
            cubes = provider.list_cubes()
            # Cehck for duplicity
            for cube in cubes:
                name = cube["name"]
                if name in cube_names:
                    raise ModelError("Duplicate cube '%s'" % name)
                cube_names.add(name)

            all_cubes += cubes

        if recursive:
            for name, ns in self.namespaces.items():
                cubes = ns.list_cubes(recursive=True)
                for cube in cubes:
                    cube["name"] = "%s.%s" % (name, cube["name"])
                all_cubes += cubes

        return all_cubes

    # TODO: change to find_dimension() analogous to the find_cube(). Let the
    # caller to perform actual dimension creation using the provider
    def dimension(self, name, locale=None, templates=None, local_only=False):
        dim = None

        for provider in self.providers:
            # TODO: use locale
            try:
                dim = provider.dimension(name, locale=locale,
                                         templates=templates)
            except NoSuchDimensionError:
                pass
            else:
                return dim

        # If we are not looking for dimension within this namespace only,
        # traverse the namespace hierarchy, if there is one
        if not local_only and self.parent:
            return self.parent.dimension(name, locale, templates)

        raise NoSuchDimensionError("Unknown dimension '%s'" % str(name), name)

    def add_provider(self, provider):
        self.providers.append(provider)

    def add_translation(self, lang, translation):
        """Registers and merges `translation` for language `lang`"""
        try:
            trans = self.translations[lang]
        except KeyError:
            trans = {}
            self.translations[lang] = trans

        # Is it a path?
        if isinstance(translation, compat.string_type):
            translation = read_json_file(translation)

        trans.update(translation)

    def translation_lookup(self, lang):
        """Returns translation in language `lang` for model object `obj`
        within `context` (cubes, dimensions, attributes, ...).  Looks in
        parent if current namespace does not have the translation."""

        lookup = []
        visited = set()

        # Find namespaces with translation language
        ns = self
        while ns and ns not in visited:
            if lang in ns.translations:
                lookup.append(ns.translations[lang])
            visited.add(ns)
            ns = ns.parent

        return lookup

