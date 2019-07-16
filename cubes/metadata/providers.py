# -*- coding: utf-8 -*-
"""Logical model model providers."""
import copy
from typing import Any, Dict, List, Optional, Set, cast

from ..errors import (
    BackendError,
    CubesError,
    ModelError,
    NoSuchCubeError,
    NoSuchDimensionError,
    TemplateRequired,
)
from ..ext import Extensible
from ..namespace import Namespace
from ..stores import Store
from ..types import JSONType
from .cube import Cube
from .dimension import Dimension
from .localization import LocalizationContext

__all__ = ["ModelProvider", "StaticModelProvider", "link_cube", "find_dimension"]

# Proposed Provider API:
#     Provider.cube() – in abstract class
#     Provider.provide_cube() – in concrete class, providers Cube object that
#         might be modified later
#     Provider.provide_dimension()
#     Provider.link_cube(cube,locale)
#     Provider.find_dimension(cube, locale)
#
# Provider is bound to namespace


class ModelProvider(Extensible, abstract=True):
    """Abstract class – factory for model object. Currently empty and used
    only to find other model providers."""

    __extension_type__ = "model_provider"

    store: Optional[Store]
    metadata: JSONType
    dimensions_metadata: Dict[str, JSONType]
    cubes_metadata: Dict[str, JSONType]

    # TODO: Don't get metadata, but arbitrary arguments.
    def __init__(self, metadata: JSONType = None) -> None:
        """Base class for model providers. Initializes a model provider and
        sets `metadata` – a model metadata dictionary.

        Subclasses should call this method at the beginning of the custom
        `__init__()`.

        If a model provider subclass has a metadata that should be pre-pended
        to the user-provided metadta, it should return it in
        `default_metadata()`.

        Subclasses should implement at least: :meth:`cubes.ModelProvider.cube`,
        :meth:`cubes.ModelProvider.dimension` and
        :meth:`cubes.ModelProvider.list_cubes` methods.
        """

        self.store = None

        # Get provider's defaults and pre-pend it to the user provided
        # metadtata.
        defaults: JSONType
        defaults = self.default_metadata()
        self.metadata = _merge_metadata(defaults, metadata or {})

        # TODO: check for duplicates
        self.dimensions_metadata = {}
        for dim in self.metadata.get("dimensions", []):
            self.dimensions_metadata[dim["name"]] = dim

        self.cubes_metadata = {}
        for cube in self.metadata.get("cubes", []):
            self.cubes_metadata[cube["name"]] = cube

        # TODO: decide which one to use
        self.options = self.metadata.get("options", {})
        self.options.update(self.metadata.get("browser_options", {}))

    def default_metadata(self, metadata: JSONType = None) -> JSONType:
        """Returns metadata that are prepended to the provided model metadata.
        `metadata` is user-provided metadata and might be used to decide what
        kind of default metadata are returned.

        The metadata are merged as follows:

        * cube lists are concatenated (no duplicity checking)
        * dimension lists are concatenated (no duplicity checking)
        * joins are concatenated
        * default mappings are updated with the model's mappings

        Default implementation returns empty metadata.
        """

        return {}

    # TODO: remove this in favor of provider configuration: store=
    def requires_store(self) -> bool:
        """Return `True` if the provider requires a store. Subclasses might
        override this method. Default implementation returns `False`"""
        return False

    # TODO: bind this automatically on provider configuration: store (see
    # requires_store() function)
    def bind(self, store: Store) -> None:
        """Set's the provider's `store`. """

        self.store = store
        self.initialize_from_store()

    def initialize_from_store(self) -> None:
        """This method is called after the provider's `store` was set.
        Override this method if you would like to perform post-initialization
        from the store."""
        pass

    def cube_options(self, cube_name: str) -> JSONType:
        """Returns an options dictionary for cube `name`. The options
        dictoinary is merged model `options` metadata with cube's `options`
        metadata if exists. Cube overrides model's global (default)
        options."""

        options = dict(self.options)
        if cube_name in self.cubes_metadata:
            cube = self.cubes_metadata[cube_name]
            # TODO: decide which one to use
            options.update(cube.get("options", {}))
            options.update(cube.get("browser_options", {}))

        return options

    def dimension_metadata(self, name: str, locale: str = None) -> JSONType:
        """Returns a metadata dictionary for dimension `name` and optional
        `locale`.

        Subclasses should override this method and call the super if they
        would like to merge metadata provided in a model file."""

        try:
            return self.dimensions_metadata[name]
        except KeyError:
            raise NoSuchDimensionError("No such dimension '%s'" % name, name)

    def cube_metadata(self, name: str, locale: str = None) -> JSONType:
        """Returns a cube metadata by combining model's global metadata and
        cube's metadata. Merged metadata dictionaries: `browser_options`,
        `mappings`, `joins`.

        Subclasses should override this method and call the super if they
        would like to merge metadata provided in a model file.

        .. note:

            If provider is caching a cube metadata, it should store a cache
            for localized version of the cube metadata.
        """

        if name in self.cubes_metadata:
            metadata = dict(self.cubes_metadata[name])
        else:
            raise NoSuchCubeError("No such cube '%s'" % name, name)

        # merge browser_options
        browser_options = self.metadata.get("browser_options", {})
        if metadata.get("browser_options"):
            browser_options.update(metadata.get("browser_options"))
        metadata["browser_options"] = browser_options

        # Merge model and cube mappings
        #
        model_mappings = self.metadata.get("mappings")
        cube_mappings = metadata.pop("mappings", {})

        if model_mappings:
            mappings = copy.deepcopy(model_mappings)
            mappings.update(cube_mappings)
        else:
            mappings = cube_mappings

        metadata["mappings"] = mappings

        # Merge model and cube joins
        #
        model_joins = self.metadata.get("joins", [])
        cube_joins = metadata.pop("joins", [])

        # model joins, if present, should be merged with cube's overrides.
        # joins are matched by the "name" key.
        if cube_joins and model_joins:
            # FIXME: [typing] Use Join named tuple
            model_join_map: Dict[str, JSONType]
            model_join_map = {}
            for join in model_joins:
                try:
                    jname = join["name"]
                except KeyError:
                    raise ModelError(
                        "Missing required 'name' key in model-level joins."
                    )

                if jname in model_join_map:
                    raise ModelError("Duplicate model-level join 'name': %s" % jname)

                model_join_map[jname] = copy.deepcopy(join)

            # Merge cube's joins with model joins by their names.
            merged_joins = []

            for join in cube_joins:
                name = join.get("name")
                if name and name in model_join_map:
                    model_join = dict(model_join_map[name])
                else:
                    model_join = {}

                model_join.update(join)
                merged_joins.append(model_join)
        else:
            merged_joins = cube_joins

        # Validate joins:
        for join in merged_joins:
            if "master" not in join:
                raise ModelError(
                    "No master in join for cube '%s' "
                    "(join name: %s)" % (name, join.get("name"))
                )
            if "detail" not in join:
                raise ModelError(
                    "No detail in join for cube '%s' "
                    "(join name: %s)" % (name, join.get("name"))
                )

        metadata["joins"] = merged_joins

        return metadata

    def list_cubes(self) -> List[JSONType]:
        """Get a list of metadata for cubes in the workspace. Result is a list
        of dictionaries with keys: `name`, `label`, `category`, `info`.

        The list is fetched from the model providers on the call of this
        method.

        Subclassees should implement this method.
        """
        raise NotImplementedError("Subclasses should implement list_cubes()")

    def has_cube(self, name: str) -> bool:
        """Returns `True` if the provider has cube `name`. Otherwise returns
        `False`."""

        return name in self.cubes_metadata

    def cube(self, name: str, locale: str = None, namespace: Namespace = None) -> Cube:
        """Returns a cube with `name` provided by the receiver. If receiver
        does not have the cube `NoSuchCube` exception is raised.

        Note: The returned cube will not have the dimensions assigned.
        It is up to the caller's responsibility to assign appropriate
        dimensions based on the cube's `dimension_links`.

        Subclasses of `ModelProvider` might override this method if they would
        like to create the `Cube` object directly.

        .. note:

            If provider is caching a cube, it should store a cache for
            localized version of the cube.
        """

        metadata = self.cube_metadata(name, locale)
        cube = Cube.from_metadata(metadata)
        link_cube(cube, locale, provider=self, namespace=namespace)

        return cube

    def dimension(
        self, name: str, templates: Dict[str, Dimension] = None, locale: str = None
    ) -> Dimension:
        """Returns a dimension with `name` provided by the receiver.
        `dimensions` is a dictionary of dimension objects where the receiver
        can look for templates. If the dimension requires a template and the
        template is missing, the subclasses should raise
        `TemplateRequired(template)` error with a template name as an
        argument.

        If the receiver does not provide the dimension `NoSuchDimension`
        exception is raised.
        """
        metadata = self.dimension_metadata(name, locale)
        return Dimension.from_metadata(metadata, templates=templates or {})


def _merge_metadata(metadata: JSONType, other: JSONType) -> JSONType:
    """See `default_metadata()` for more information."""

    metadata = dict(metadata)
    other = dict(other)

    cubes = metadata.pop("cubes", []) + other.pop("cubes", [])
    if cubes:
        metadata["cubes"] = cubes

    dims = metadata.pop("dimensions", []) + other.pop("dimensions", [])
    if dims:
        metadata["dimensions"] = dims

    joins = metadata.pop("joins", []) + other.pop("joins", [])
    if joins:
        metadata["joins"] = joins

    mappings = metadata.pop("mappings", {})
    mappings.update(other.pop("mappings", {}))
    if mappings:
        metadata["mappings"] = mappings

    metadata.update(other)

    return metadata


# TODO: make this FileModelProvider
class StaticModelProvider(ModelProvider, name="static"):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Initialization code goes here...

    def list_cubes(self) -> List[JSONType]:
        """Returns a list of cubes from the metadata."""
        cubes = []

        for cube in self.metadata.get("cubes", []):
            info = {
                "name": cube["name"],
                "label": cube.get("label", cube["name"]),
                "category": (
                    cube.get("category") or cube.get("info", {}).get("category")
                ),
                "info": cube.get("info", {}),
            }
            cubes.append(info)

        return cubes


# TODO: add tests
# TODO: needs to be reviewed
def link_cube(
    cube: Cube,
    locale: Optional[str],
    provider: ModelProvider = None,
    namespace: Namespace = None,
    ignore_missing: bool = False,
) -> Cube:
    """Links dimensions to the `cube` in the `context` object. The `context`
    object should implement a function `dimension(name, locale, namespace,
    provider)`. Modifies cube in place, returns the cube.
    """
    # TODO: change this to: link_cube(cube, locale, namespace, provider)

    # Assumption: empty cube

    linked: Set[str] = set()

    for dim_name in cube.dimension_links.keys():
        if dim_name in linked:
            raise ModelError(f"Dimension '{dim_name}' linked twice")

        try:
            dim = find_dimension(
                dim_name, locale, provider=provider, namespace=namespace
            )
        except TemplateRequired as e:
            raise ModelError("Dimension template '%s' missing" % dim_name)

        if not dim and not ignore_missing:
            raise CubesError(f"Dimension '{dim_name}' not found.")

        cube.link_dimension(dim)
        linked.add(dim_name)

    return cube


# TODO: add tests
def find_dimension(
    name: str,
    locale: Optional[str] = None,
    provider: Optional[ModelProvider] = None,
    namespace: Optional[Namespace] = None,
) -> Dimension:
    """Returns a localized dimension with `name`. Raises
    `NoSuchDimensionError` when no model published the dimension. Raises
    `RequiresTemplate` error when model provider requires a template to be
    able to provide the dimension, but such template is not a public
    dimension.

    The standard lookup when linking a cube is:

    1. look in the provider
    2. look in the namespace – all providers within that namespace
    """

    # Collected dimensions – to be used as templates
    templates: Dict[str, Dimension] = {}

    # Assumption: all dimensions that are to be used as templates should
    # be public dimensions. If it is a private dimension, then the
    # provider should handle the case by itself.
    missing: List[str]
    missing = [name]

    while missing:
        dimension: Dimension

        name = missing.pop()

        # First give a chance to provider, then to namespace
        requierd_template: Optional[str]
        required_template = None

        try:
            dimension = _lookup_dimension(name, templates, namespace, provider)
        except TemplateRequired as e:
            required_template = e.template
        else:
            templates[name] = dimension

        if required_template in templates:
            raise BackendError(
                "Some model provider didn't make use of "
                "dimension template '%s' for '%s'" % (required_template, name)
            )

        if required_template:
            missing.append(name)
            if required_template in missing:
                raise ModelError(
                    "Dimension templates cycle in '%s'" % required_template
                )
            missing.append(required_template)

    if namespace is not None and locale is not None:
        lookup = namespace.translation_lookup(locale)

        if lookup is not None and dimension is not None:
            # TODO: pass lookup instead of jsut first found translation
            context = LocalizationContext(lookup[0])
            trans = context.object_localization("dimensions", "inner")
            dimension = cast(Dimension, dimension.localized(trans))

    return dimension


# TODO: add tests
def _lookup_dimension(
    name: str,
    templates: Dict[str, Dimension],
    namespace: Optional[Namespace],
    provider: Optional[ModelProvider],
) -> Dimension:
    """Look-up a dimension `name` in `provider` and then in `namespace`.

    `templates` is a dictionary with already instantiated dimensions that
    can be used as templates.
    """

    dimension = None

    # 1. look in the povider
    if provider:
        try:
            dimension = provider.dimension(name, templates=templates)
        except NoSuchDimensionError:
            pass
        else:
            return dimension

    # 2. Look in the namespace
    if namespace:
        return namespace.dimension(name, templates=templates)

    raise NoSuchDimensionError("Dimension '%s' not found" % name, name=name)
