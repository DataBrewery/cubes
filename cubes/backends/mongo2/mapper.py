# -*- coding: utf-8 -*-
"""Logical to Physical Mapper for MongoDB"""

import collections
import copy
from cubes.common import get_logger
from cubes.errors import *
from cubes.mapper import Mapper
from bson.objectid import ObjectId
import datetime

__all__ = (
    "MongoCollectionMapper"
)

DEFAULT_KEY_FIELD = "_id"

MONGO_TYPES = {
    'string': str,
    'str': str,
    'objectid': ObjectId,
    'oid': ObjectId,
    'integer': int,
    'int': int,
    'float': float,
    'double': float
}

MONGO_EVAL_NS = {
    'datetime': datetime
}

"""Physical reference to a mongo document field."""
class MongoDocumentField(object):
    def __init__(self, database, collection, field, match, project, group,
                 encode, decode, type=None):
        """Creates a mongo document field."""

        self.database = database
        self.collection = collection
        self.field = field
        self.match = match
        self.project = project
        self.group = None

        if group:
            self.group = copy.deepcopy(group)

        self.encode = lambda x: x
        if encode:
            self.encode = eval(compile(encode, '__encode__', 'eval'), copy.copy(MONGO_EVAL_NS))

        self.decode = lambda x: x
        if decode:
            self.decode = eval(compile(decode, '__decode__', 'eval'), copy.copy(MONGO_EVAL_NS))

        self.type = MONGO_TYPES.get(str('string' if type is None else type).lower(), str)

    def group_expression(self):
        return copy.deepcopy(self.group) if self.group else self.group

    def match_expression(self, value, op=None, for_project=False):
        value = self.encode(value)
        field_name = ("$%s" % self.field) if for_project else self.field
        if op is None or (op == '$eq' and not for_project):
            return { field_name : value }
        elif for_project:
            return { op : [ field_name, value ] }
        else:
            return { field_name : { op : value } }

    def project_expression(self):
        if self.project:
            return copy.deepcopy(self.project)
        else:
            return "$%s" % self.field


def coalesce_physical(mapper, ref):
    if isinstance(ref, basestring):
        return MongoDocumentField(mapper.database, mapper.collection, ref,
                                  None, None, None, None, None, None)
    elif isinstance(ref, dict):
        return MongoDocumentField(
            ref.get('database', mapper.database),
            ref.get('collection', mapper.collection),
            ref.get('field'),
            ref.get('match'),
            ref.get('project'),
            ref.get('group'),
            ref.get("encode"),
            ref.get("decode"),
            ref.get("type")
            )
    else:
        raise BackendError("Number of items in mongo document field reference"
                           " should be 1 (field name) or a dict of (field, "
                           "match, project, encode, decode)")


class MongoCollectionMapper(Mapper):
    """Mapper is core clas for translating logical model to physical
    database schema.
    """
    def __init__(self, cube, database, collection, mappings=None, **options):

        """A mongo collection mapper for a cube. The mapper creates required
        fields, project and match expressions, and encodes/decodes using
        provided python lambdas.

        Attributes:

        * `cube` - mapped cube
        * `mappings` – dictionary containing mappings

        `mappings` is a dictionary where keys are logical attribute references
        and values are mongo document field references. The keys are mostly in the
        form:

        * ``attribute`` for measures and fact details
        * ``dimension.attribute`` for dimension attributes

        The values might be specified as strings in the form ``field``
        (covering most of the cases) or as a dictionary with keys ``database``,
        ``collection`` and ``field`` for more customized references.

        """

        super(MongoCollectionMapper, self).__init__(cube, **options)

        self.database = database
        self.collection = collection
        self.mappings = mappings or cube.mappings

    def physical(self, attribute, locale=None):
        """Returns physical reference as tuple for `attribute`, which should
        be an instance of :class:`cubes.model.Attribute`. If there is no
        dimension specified in attribute, then fact table is assumed. The
        returned object is a MongoDocumentField object.
        """

        reference = None
        dimension = attribute.dimension

        # Try to get mapping if exists
        if self.cube.mappings:
            logical = self.logical(attribute, locale)

            # TODO: should default to non-localized reference if no mapping
            # was found?
            mapped_ref = self.cube.mappings.get(logical)

            if mapped_ref:
                reference = coalesce_physical(self, mapped_ref)

        # No mappings exist or no mapping was found - we are going to create
        # default physical reference
        if not reference:
            field_name = attribute.name

            if locale:
                field_name += "_" + locale

            reference = coalesce_physical(self, field_name)

        return reference

