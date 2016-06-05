# -*- coding: utf-8 -*-

from __future__ import absolute_import
from . import compat
# Global Context – top level namespace and objects in other namespaces
# Local Context - within object being translated

# TODO: work in progress
# TODO: rename to something nicer
# TODO: reuse the lookup function
# TODO: Change this to use translation lookup instead of just one translation

class ModelObjectLocalizationContext(object):
    def __init__(self, translation, context, object_type, object_name):
        self.translation = translation
        self.object_type = object_type
        self.object_name = object_name
        self.context = context

    def get(self, key, default=None):
        try:
            return self.translation[key]
        except KeyError:
            return self.context.get(self.object_type, self.object_name, key,
                                    default)

    def object_localization(self, object_type, name):
        try:
            objects = self.translation[object_type]
        except KeyError:
            objects = self.context.translation.get(object_type, {})

        try:
            trans = objects[name]
        except KeyError:
            return ModelObjectLocalizationContext({}, self.context,
                                              object_type, name)

        # Make string-only translations as translations of labels
        if isinstance(trans, compat.string_type):
            trans = {"label": trans}

        return ModelObjectLocalizationContext(trans, self.context,
                                              object_type, name)

class LocalizationContext(object):
    def __init__(self, translation, parent=None):
        self.translation = translation
        self.parent = parent

    def object_localization(self, object_type, name):
        try:
            objects = self.translation[object_type]
        except KeyError:
            return ModelObjectLocalizationContext({}, self, object_type, name)

        try:
            trans = objects[name]
        except KeyError:
            return ModelObjectLocalizationContext({}, self, object_type, name)

        # Make string-only translations as translations of labels
        if isinstance(trans, compat.string_type):
            trans = {"label": trans}

        return ModelObjectLocalizationContext(trans, self, object_type, name)

    def get(self, object_type, object_name, key, default=None):
        try:
            objects = self.translation[object_type]
        except KeyError:
            return default

        try:
            trans = objects[object_name]
        except KeyError:
            return default

        # Accept plain label translation – string only, no dictionary (similar
        # as above)
        if isinstance(trans, compat.string_type):
            if key == "label":
                return trans
            else:
                return default

        return trans.get(key, default)

    def _get_translation(self, obj, type_):
        """Returns translation in language `lang` for model object `obj` of
        type `type_`. The type can be: ``cube`` or ``dimension``. Looks in
        parent if current namespace does not have the translation."""

        lookup = []
        visited = set()

        # Find namespaces with translation language
        ns = self.namespace
        while ns and ns not in visited:
            if self.lang in ns.translations:
                lookup.append(ns.translation[lang])
            visited.add(ns)
            ns = ns.parent

        lookup_map = {
            "cube": "cubes",
            "dimension": "dimensions",
            "defaults": "defaults"
        }

        objkey = lookup_map[type_]

        for trans in lookup:
            if objkey in trans and obj in trans[objkey]:
                return trans[objkey][obj]

        return None

