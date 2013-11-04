# -*- coding=utf -*-

import os.path
import json
from collections import namedtuple
from .extensions import get_namespace, initialize_namespace
from .browser import Cell, cut_from_string, cut_from_dict
from .errors import *
from .common import read_json_file, sorted_dependencies

__all__ = (
    "create_authorizer",
    "Authorizer",
    "SimpleAuthorizer",
    "NotAuthorized",
    "right_from_dict"
)

ALL_CUBES_WILDCARD = '*'

class NotAuthorized(UserError):
    """Raised when user is not authorized for the request."""
    # Note: This is not called NotAuthorizedError as it is not in fact an
    # error, it is just type of signal.


def create_authorizer(name, **options):
    """Gets a new instance of an authorizer with name `name`."""

    ns = get_namespace("authorizers")
    if not ns:
        ns = initialize_namespace("authorizers", root_class=Authorizer,
                                  suffix="_authorizer",
                                  option_checking=True)
    try:
        factory = ns[name]
    except KeyError:
        raise ConfigurationError("Unknown authorizer '%s'" % name)

    return factory(**options)


class Authorizer(object):
    def authorize(self, token, cubes):
        """Returns list of authorized cubes from `cubes`. If none of the cubes
        are authorized an empty list is returned.

        Default implementation returs the same `cubes` list as provided.
        """
        return cubes

    def restricted_cell(self, token, cube, cell=None):
        """Restricts the `cell` for `cube` according to authorization by
        `token`. If no cell is provided or the cell is empty then returns
        the restriction cell. If there is no restriction, returns the original
        `cell` if provided or `None`.
        """
        return cell


class NoopAuthorizer(Authorizer):
    def __init__(self):
        super(NoopAuthorizer, self).__init__()


class _SimpleAccessRight(object):
    def __init__(self, roles, allow_cubes, deny_cubes, cube_restrictions):
        self.roles = set(roles) if roles else set([])
        self.allow_cubes = set(allow_cubes) if allow_cubes else set([])
        self.deny_cubes = set(deny_cubes) if deny_cubes else set([])
        self.cube_restrictions = cube_restrictions or {}

    def merge(self, other):
        """Merge `right` with the receiver:

        * `allow_cubes` are merged (union)
        * `deny_cubes` are merged (union)
        * `cube_restrictions` from `other` with same cube replace restrictions
          from the receiver"""

        self.roles |= other.roles
        self.allow_cubes |= other.allow_cubes
        self.deny_cubes |= other.deny_cubes

        for cube, restrictions in other.cube_restrictions.iteritems():
            if not cube in self.cube_restrictions:
                self.cube_restrictions[cube] = restrictions
            else:
                mine = self.cube_restrictions[cube]
                mine += restrictions

    def is_allowed(self, cube_name):
        return (self.allow_cubes \
                    and (cube_name in self.allow_cubes \
                            or ALL_CUBES_WILDCARD in self.allow_cubes)) \
                or \
                    (self.deny_cubes \
                    and (cube_name not in self.deny_cubes \
                            and ALL_CUBES_WILDCARD not in self.deny_cubes))

    def to_dict(self):
        return {
            "roles": list(self.roles),
            "allowed_cubes": list(self.allow_cubes),
            "denied_cubes": list(self.deny_cubes),
            "cube_restrictions": dict(self.cube_restrictions)
        }


def right_from_dict(info):
    return _SimpleAccessRight(
               info.get('roles'), info.get('allowed_cubes'),
               info.get('denied_cubes'), info.get('cube_restrictions')
           )

class SimpleAuthorizer(Authorizer):
    __options__ = [
        {
            "name": "rights_file",
            "description": "JSON file with access rights",
            "type": "string"
        },
        {
            "name": "roles_file",
            "description": "JSON file with access right roles",
            "type": "string"
        },

    ]

    def __init__(self, rights_file=None, roles_file=None, roles=None,
                 rights=None, **options):
        """Creates a simple JSON-file based authorizer. Reads data from
        `rights_file` and `roles_file` and merge them with `roles` and
        `rights` dictionaries respectively."""

        super(SimpleAuthorizer, self).__init__()

        roles = roles or {}
        rights = rights or {}

        if roles_file:
            content = read_json_file(roles_file, "access roles")
            roles.update(content)

        if rights_file:
            content = read_json_file(rights_file, "access rights")
            rights.update(content)

        self.roles = {}
        self.rights = {}

        # Process the roles
        for key, info in roles.items():
            role = right_from_dict(info)
            self.roles[key] = role

        deps = dict((name, role.roles) for name, role in self.roles.items())
        order = sorted_dependencies(deps)

        for name in order:
            role = self.roles[name]
            for parent_name in role.roles:
                parent = self.roles[parent_name]
                role.merge(parent)

        # Process rights
        for key, info in rights.items():
            right = right_from_dict(info)
            self.rights[key] = right

            for role_name in list(right.roles):
                role = self.roles[role_name]
                right.merge(role)

    def right(self, token):
        try:
            right = self.rights[token]
        except KeyError:
            raise NotAuthorized("Unknown access right '%s'" % token)
        return right

    def authorize(self, token, cubes):
        try:
            right = self.right(token)
        except NotAuthorized:
            return []

        authorized = []

        for cube in cubes:
            cube_name = str(cube)

            if right.is_allowed(cube_name):
                authorized.append(cube)

        return authorized

    def restricted_cell(self, token, cube, cell):
        right = self.right(token)

        cuts = right.cube_restrictions.get(cube.name)

        # Append cuts for "any cube"
        any_cuts = right.cube_restrictions.get(ALL_CUBES_WILDCARD, [])
        if any_cuts:
            cuts += any_cuts

        if cuts:
            restriction_cuts = []
            for cut in cuts:
                if isinstance(cut, basestring):
                    cut = cut_from_string(cut, cube)
                else:
                    cut = cut_from_dict(cut)
                restriction_cuts.append(cut)

            restriction = Cell(cube, restriction_cuts)
        else:
            restriction = None

        if not restriction:
            return cell
        elif cell:
            return cell & restriction
        else:
            return restriction

