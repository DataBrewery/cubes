# -*- coding=utf -*-

import os.path
import json
from collections import namedtuple, defaultdict
from .extensions import get_namespace, initialize_namespace
from .browser import Cell, cut_from_string, cut_from_dict
from .browser import string_to_drilldown
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

    def hierarchy_limits(self, token, cube):
        """Returns a list of tuples: (`dimension`, `hierarchy`, `level`)."""
        # TODO: provisional feature, might change
        return []


class NoopAuthorizer(Authorizer):
    def __init__(self):
        super(NoopAuthorizer, self).__init__()


class _SimpleAccessRight(object):
    def __init__(self, roles, allow_cubes, deny_cubes, cell_restrictions,
                 hierarchy_limits):
        self.roles = set(roles) if roles else set([])
        self.cell_restrictions = cell_restrictions or {}

        self.hierarchy_limits = defaultdict(list)

        if hierarchy_limits:
            for cube, limits in hierarchy_limits.items():
                for limit in limits:
                    if isinstance(limit, basestring):
                        limit = string_to_drilldown(limit)
                    self.hierarchy_limits[cube].append(limit)

        self.hierarchy_limits = dict(self.hierarchy_limits)

        self.allow_cubes = set(allow_cubes) if allow_cubes else set([])
        self.deny_cubes = set(deny_cubes) if deny_cubes else set([])
        self._get_patterns()

    def _get_patterns(self):
        self.allow_cube_suffix = []
        self.allow_cube_prefix = []
        self.deny_cube_suffix = []
        self.deny_cube_prefix = []

        for cube in self.allow_cubes:
            if cube.startswith("*"):
                self.allow_cube_suffix.append(cube[1:])
            if cube.endswith("*"):
                self.allow_cube_prefix.append(cube[:-1])

        for cube in self.deny_cubes:
            if cube.startswith("*"):
                self.deny_cube_suffix.append(cube[1:])
            if cube.endswith("*"):
                self.deny_cube_prefix.append(cube[:-1])

    def merge(self, other):
        """Merge `right` with the receiver:

        * `allow_cubes` are merged (union)
        * `deny_cubes` are merged (union)
        * `cube_restrictions` from `other` with same cube replace restrictions
          from the receiver"""

        self.roles |= other.roles
        self.allow_cubes |= other.allow_cubes
        self.deny_cubes |= other.deny_cubes

        for cube, restrictions in other.cell_restrictions.iteritems():
            if not cube in self.cube_restrictions:
                self.cell_restrictions[cube] = restrictions
            else:
                self.cell_restrictions[cube] += restrictions

        for cube, limits  in other.hierarchy_limits.iteritems():
            if not cube in self.hierarchy_limits:
                self.hierarchy_limits[cube] = limits
            else:
                self.hierarchy_limits[cube] += limits

        self._get_patterns()

    def is_allowed(self, name):
        allow = True
        if self.allow_cubes:
            if (name in self.allow_cubes) or \
                        (ALL_CUBES_WILDCARD in self.allow_cubes):
                allow = True

            if not allow and self.allow_cube_prefix:
                allow = any(name.startswith(p) for p in self.allow_cube_prefix)
            if not allow and self.allow_cube_suffix:
                allow = any(name.endswith(p) for p in self.allow_cube_suffix)

        else:
            allow = True

        deny = False
        if self.deny_cubes:
            if (name in self.deny_cubes) or \
                        (ALL_CUBES_WILDCARD in self.deny_cubes):
                deny = True

            if not deny and self.deny_cube_prefix:
                deny = any(name.startswith(p) for p in self.deny_cube_prefix)
            if not deny and self.deny_cube_suffix:
                deny = any(name.endswith(p) for p in self.deny_cube_suffix)

        else:
            deny = False


        return allow and not deny

    def to_dict(self):
        as_dict = {
            "roles": list(self.roles),
            "allowed_cubes": list(self.allow_cubes),
            "denied_cubes": list(self.deny_cubes),
            "cell_restrictions": self.cell_restrictions,
            "hierarchy_limits": self.hierarchy_limits
        }

        return as_dict


def right_from_dict(info):
    return _SimpleAccessRight(
               roles=info.get('roles'),
               allow_cubes=info.get('allowed_cubes'),
               deny_cubes=info.get('denied_cubes'),
               cell_restrictions=info.get('cell_restrictions'),
               hierarchy_limits=info.get('hierarchy_limits')
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

        cuts = right.cell_restrictions.get(cube.name)

        # Append cuts for "any cube"
        any_cuts = right.cell_restrictions.get(ALL_CUBES_WILDCARD, [])
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

    def hierarchy_limits(self, token, cube):
        right = self.right(token)

        return right.hierarchy_limits.get(str(cube), [])


