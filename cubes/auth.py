# -*- coding=utf -*-

import os.path
import json
from collections import namedtuple
from .extensions import get_namespace, initialize_namespace
from .browser import Cell
from .errors import *
from .common import read_json_file, sorted_dependencies

__all__ = (
    "create_authorizer",
    "Authorizer",
    "SimpleAuthorizer",
    "NotAuthorized"
)


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
    def cube_is_allowed(self, token):
        """Return a list of allowed cubes for authorization `token`."""
        raise NotImplementedError

    def authorize(self, token, cube):
        """Returns appropriated `cell` within `cube` for authorization token
        `token`. The `token` is specific to concrete authorizer object.

        If `token` does not authorize access to the cube a NotAuthorized exception is
        raised."""
        raise NotImplementedError

    def restricted_cell(self, token, cube, cell=None):
        """Restricts the `cell` for `cube` according to authorization by
        `token`. If no cell is provided or the cell is empty then returns
        the restriction cell. If there is no restriction, returns the original
        `cell` if provided or `None`.
        """
        raise NotImplemented

class NoopAuthorizer(Authorizer):
    def __init__(self):
        super(NoopAuthorizer, self).__init__()

    def authorize(self, token, cube, cell=None):
        return None

    def restricted_cell(self, token, cube, cell):
        return None


class _SimpleAccessRight(object):
    def __init__(self, roles, allow_cubes, deny_cubes, cube_restrictions):
        self.roles = roles or []
        self.allow_cubes = set(allow_cubes) if allow_cubes else set()
        self.deny_cubes = set(deny_cubes) if deny_cubes else set()
        self.cube_restrictions = cube_restrictions or {}

    def merge(self, other):
        """Merge `right` with the receiver:

        * `allow_cubes` are merged (union)
        * `deny_cubes` are merged (union)
        * `cube_restrictions` from `other` with same cube replace restrictions
          from the receiver"""

        self.allow_cubes |= other.allow_cubes
        self.deny_cubes |= other.deny_cubes

        for cube, restrictions in other.cube_restrictions:
            if not cube in self.cube_restrictions:
                self.cube_restrictions = list(other.cube_restrictions)
            else:
                mine = self.cube_restrictions.get(cube)
                mine += restritions


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
            role = _SimpleAccessRight(roles=info.get("roles"),
                                      allow_cubes=info.get("allow_cubes"),
                                      deny_cubes=info.get("deny_cubes"),
                                      cube_restrictions=info.get("cube_restrictions"))
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
            right = _SimpleAccessRight(roles=info.get("roles"),
                                       allow_cubes=info.get("allow_cubes"),
                                       deny_cubes=info.get("deny_cubes"),
                                       cube_restrictions=info.get("cube_restrictions"))
            self.rights[key] = right

            for role_name in right.roles:
                role = self.roles[role_name]
                right.merge(role)

    def right(self, token):
        try:
            right = self.rights[token]
        except KeyError:
            raise NotAuthorized("Unknown access right '%s'" % token)
        return right

    def authorize(self, token, cube):
        right = self.right(token)

        cube_name = str(cube)

        if (right.allow_cubes and cube_name not in right.allow_cubes) \
                or (right.deny_cubes and cube_name in right.deny_cubes):
            raise NotAuthorized("Unauthorized cube '%s' for '%s'"
                                % (cube_name, token))

    def restricted_cell(self, token, cube, cell):
        right = self.right(token)

        cuts = right.cube_restrictions.get(cube.name)

        if cuts:
            cuts = [cut_from_dict(cut) for cut in cuts]
            restriction = Cell(cube, cuts)
        else:
            restriction = None

        if not restriction:
            return cell
        elif cell:
            return cell + restriction
        else:
            return restriction

