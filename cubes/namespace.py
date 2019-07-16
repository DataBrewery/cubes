# -*- coding: utf-8 -*-
# TODO: This module requires redesign if not removal. Namespaces are not good
# idea if one of the objectives is to preserve model quality.

from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .common import read_json_file
from .errors import ModelError, NoSuchCubeError, NoSuchDimensionError
from .metadata.dimension import Dimension
from .types import JSONType

# from .metadata.providers import ModelProvider
# FIXME: [Tech-debt] This needs to go away with redesign of namespaces/providers
# FIXME: [typing] Workaround for circular dependency
ModelProvider = Any


__all__ = ["Namespace"]


class Namespace:

    parent: Optional["Namespace"]
    name: Optional[str]
    namespaces: Dict[str, "Namespace"]
    providers: List[ModelProvider]
    translations: Dict[str, JSONType]

    def __init__(self, name: Optional[str] = None, parent: "Namespace" = None) -> None:
        """Creates a cubes namespace – an object that provides model objects
        from the providers."""
        # TODO: Assign this on __init__, namespaces should not be freely
        # floating until anchored in another namespace
        self.parent = parent
        self.name = name
        self.namespaces = {}
        self.providers = []
        self.translations = {}

    def namespace(
        self, path: Union[str, List[str]], create: bool = False
    ) -> Tuple["Namespace", Optional[str]]:
        """Returns a tuple (`namespace`, `remainder`) where `namespace` is the
        deepest namespace in the namespace hierarchy and `remainder` is the
        remaining part of the path that has no namespace (is an object name or
        contains part of external namespace).

        If path is empty or not provided then returns self.

        If `create` is `True` then the deepest namespace is created if it does
        not exist.
        """

        if not path:
            return (self, None)

        if isinstance(path, str):
            path_elements = path.split(".")
        else:
            path_elements = path

        namespace = self
        for i, element in enumerate(path_elements):
            remainder = path_elements[i + 1 :]
            if element in namespace.namespaces:
                namespace = namespace.namespaces[element]
                found = True
            else:
                remainder = path_elements[i:]
                break

        if not create:
            return (namespace, ".".join(remainder) or None)
        else:
            for element in remainder:
                namespace = namespace.create_namespace(element)

            return (namespace, None)

    def create_namespace(self, name: str) -> "Namespace":
        """Create a namespace `name` in the receiver."""
        if self.name:
            nsname = f"{self.name}.{name}"
        else:
            nsname = name

        namespace = Namespace(nsname, parent=self)
        self.namespaces[name] = namespace

        return namespace

    def find_cube(self, cube_ref: str) -> Tuple["Namespace", ModelProvider, str]:
        """Returns a tuple (`namespace`, `provider`, `basename`) where
        `namespace` is a namespace conaining `cube`, `provider` providers the
        model for the cube and `basename` is a name of the `cube` within the
        `namespace`. For example: if cube is ``slicer.nested.cube`` and there
        is namespace ``slicer`` then that namespace is returned and the
        `basename` will be ``nested.cube``.

        Raises `NoSuchCubeError` when there is no cube with given
        reference.
        """

        path: List[str]

        cube_ref = str(cube_ref)

        split: List[str]
        split = cube_ref.split(".")

        if len(split) > 1:
            path = split[0:-1]
            cube_ref = split[-1]
        else:
            path = []
            cube_ref = cube_ref

        (namespace, remainder) = self.namespace(path)

        if remainder:
            basename = f"{remainder}.{cube_ref}"
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
            raise NoSuchCubeError(f"Unknown cube '{cube_ref}'", cube_ref)

        return (namespace, provider, basename)

    def list_cubes(self, recursive: bool = False) -> List[JSONType]:
        """Retursn a list of cube info dictionaries with keys: `name`, `label`,
        `description`, `category` and `info`."""

        all_cubes: List[JSONType]
        all_cubes = []
        cube_names: Set[str]
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
                    cube["name"] = "{}.{}".format(name, cube["name"])
                all_cubes += cubes

        return all_cubes

    # TODO: change to find_dimension() analogous to the find_cube(). Let the
    # caller to perform actual dimension creation using the provider
    def dimension(
        self,
        name: str,
        locale: str = None,
        templates: Dict[str, Dimension] = None,
        local_only: bool = False,
    ) -> Dimension:

        dim: Dimension

        for provider in self.providers:
            # TODO: use locale
            try:
                dim = provider.dimension(name, locale=locale, templates=templates)
            except NoSuchDimensionError:
                pass
            else:
                return dim

        # If we are not looking for dimension within this namespace only,
        # traverse the namespace hierarchy, if there is one
        if not local_only and self.parent is not None:
            return self.parent.dimension(name, locale, templates)

        raise NoSuchDimensionError(f"Unknown dimension '{name}'", name)

    def add_provider(self, provider: ModelProvider) -> None:
        self.providers.append(provider)

    def add_translation(self, lang: str, translation: JSONType) -> None:
        """Registers and merges `translation` for language `lang`"""
        try:
            trans = self.translations[lang]
        except KeyError:
            trans = {}
            self.translations[lang] = trans

        # Is it a path?
        if isinstance(translation, str):
            translation = read_json_file(translation)

        trans.update(translation)

    def translation_lookup(self, lang: str) -> List[JSONType]:
        """Returns translation in language `lang` for model object `obj` within
        `context` (cubes, dimensions, attributes, ...).

        Looks in parent if current namespace does not have the
        translation.
        """

        lookup: List[JSONType]
        lookup = []
        visited: Set["Namespace"]
        visited = set()

        # Find namespaces with translation language
        ns = self

        while ns is not None and ns not in visited:
            if lang in ns.translations:
                lookup.append(ns.translations[lang])
            visited.add(ns)

            if ns.parent is None:
                break
            else:
                ns = ns.parent

        return lookup
