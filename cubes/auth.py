# -*- encoding: utf-8 -*-

from __future__ import absolute_import

import os.path
from collections import defaultdict
from .cells import Cell, cut_from_string, cut_from_dict, PointCut
from .model import string_to_dimension_level
from .errors import UserError, ConfigurationError, NoSuchDimensionError
from .common import read_json_file, sorted_dependencies
from . import compat

__all__ = (
    "Authorizer",
    "SimpleAuthorizer",
    "AuthorizationError",
    "NotAuthorized",
    "right_from_dict"
)

ALL_CUBES_WILDCARD = '*'

class AuthorizationError(UserError):
    """Raised when there is any authorization-related error. Use
    more specific `NotAuthorized` when access right is denied."""
    pass

class NotAuthorized(AuthorizationError):
    """Raised when user is not authorized for the request."""
    # Note: This is not called NotAuthorizedError as it is not in fact an
    # error, it is just type of signal.

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
    def __init__(self, roles, allowed_cubes, denied_cubes, cell_restrictions,
                 hierarchy_limits):
        self.roles = set(roles) if roles else set([])
        self.cell_restrictions = cell_restrictions or {}

        self.hierarchy_limits = defaultdict(list)

        if hierarchy_limits:
            for cube, limits in hierarchy_limits.items():
                for limit in limits:
                    if isinstance(limit, compat.string_type):
                        limit = string_to_dimension_level(limit)
                    self.hierarchy_limits[cube].append(limit)

        self.hierarchy_limits = dict(self.hierarchy_limits)

        self.allowed_cubes = set(allowed_cubes) if allowed_cubes else set([])
        self.denied_cubes = set(denied_cubes) if denied_cubes else set([])
        self._get_patterns()

    def _get_patterns(self):
        self.allowed_cube_suffix = []
        self.allowed_cube_prefix = []
        self.denied_cube_suffix = []
        self.denied_cube_prefix = []

        for cube in self.allowed_cubes:
            if cube.startswith("*"):
                self.allowed_cube_suffix.append(cube[1:])
            if cube.endswith("*"):
                self.allowed_cube_prefix.append(cube[:-1])

        for cube in self.denied_cubes:
            if cube.startswith("*"):
                self.denied_cube_suffix.append(cube[1:])
            if cube.endswith("*"):
                self.denied_cube_prefix.append(cube[:-1])

    def merge(self, other):
        """Merge `right` with the receiver:

        * `allowed_cubes` are merged (union)
        * `denied_cubes` are merged (union)
        * `cell_restrictions` from `other` with same cube replace restrictions
          from the receiver"""

        self.roles |= other.roles
        self.allowed_cubes |= other.allowed_cubes
        self.denied_cubes |= other.denied_cubes

        for cube, restrictions in other.cell_restrictions.items():
            if not cube in self.cell_restrictions:
                self.cell_restrictions[cube] = restrictions
            else:
                self.cell_restrictions[cube] += restrictions

        for cube, limits  in other.hierarchy_limits.items():
            if not cube in self.hierarchy_limits:
                self.hierarchy_limits[cube] = limits
            else:
                self.hierarchy_limits[cube] += limits

        self._get_patterns()

    def is_allowed(self, name, allow_after_denied=True):

        allow = False
        if self.allowed_cubes:
            if (name in self.allowed_cubes) or \
                        (ALL_CUBES_WILDCARD in self.allowed_cubes):
                allow = True

            if not allow and self.allowed_cube_prefix:
                allow = any(name.startswith(p) for p in self.allowed_cube_prefix)
            if not allow and self.allowed_cube_suffix:
                allow = any(name.endswith(p) for p in self.allowed_cube_suffix)

        deny = False
        if self.denied_cubes:
            if (name in self.denied_cubes) or \
                        (ALL_CUBES_WILDCARD in self.denied_cubes):
                deny = True

            if not deny and self.denied_cube_prefix:
                deny = any(name.startswith(p) for p in self.denied_cube_prefix)
            if not deny and self.denied_cube_suffix:
                deny = any(name.endswith(p) for p in self.denied_cube_suffix)

        """
        Four cases:
            - allow match, no deny match
              * allow_deny: allowed
              * deny_allow: allowed
            - no allow match, deny match
              * allow_deny: denied
              * deny_allow: denied
            - no match in either
              * allow_deny: denied
              * deny_allow: allowed
            - match in both
              * allow_deny: denied
              * deny_allow: allowed
        """

        # deny_allow
        if allow_after_denied:
            return allow or not deny
        # allow_deny
        else:
            return allow and not deny

    def to_dict(self):
        as_dict = {
            "roles": list(self.roles),
            "allowed_cubes": list(self.allowed_cubes),
            "denied_cubes": list(self.denied_cubes),
            "cell_restrictions": self.cell_restrictions,
            "hierarchy_limits": self.hierarchy_limits
        }

        return as_dict


def right_from_dict(info):
    return _SimpleAccessRight(
        roles=info.get('roles'),
        allowed_cubes=info.get('allowed_cubes'),
        denied_cubes=info.get('denied_cubes'),
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
        {
            "name": "order",
            "description": "Order of allow/deny",
            "type": "string",
            "values": ["allow_deny", "deny_allow"]
        },
        {
            "name": "guest",
            "description": "Name of the 'guest' role",
            "type": "string",
        },

    ]

    def __init__(self, rights_file=None, roles_file=None, roles=None,
                 rights=None, identity_dimension=None, order=None,
                 guest=None, **options):
        """Creates a simple JSON-file based authorizer. Reads data from
        `rights_file` and `roles_file` and merge them with `roles` and
        `rights` dictionaries respectively."""

        super(SimpleAuthorizer, self).__init__()

        roles = roles or {}
        rights = rights or {}

        if roles_file and not os.path.isabs(roles_file):
            roles_file = os.path.join(options["cubes_root"], roles_file)

        if rights_file and not os.path.isabs(rights_file):
            rights_file = os.path.join(options["cubes_root"], rights_file)

        if roles_file:
            content = read_json_file(roles_file, "access roles")
            roles.update(content)

        if rights_file:
            content = read_json_file(rights_file, "access rights")
            rights.update(content)

        self.roles = {}
        self.rights = {}
        self.guest = guest or None

        order = order or "deny_allow"

        if order == "allow_deny":
            self.allow_after_denied = False
        elif order == "deny_allow":
            self.allow_after_denied = True
        else:
            raise ConfigurationError("Unknown allow/deny order: %s" % order)

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

        if identity_dimension:
            if isinstance(identity_dimension, compat.string_type):
                (dim, hier, _) = string_to_dimension_level(identity_dimension)
            else:
                (dim, hier) = identity_dimension[:2]
            self.identity_dimension = dim
            self.identity_hierarchy = hier
        else:
            self.identity_dimension = None
            self.identity_hierarchy = None

    def expand_roles(self, info):
        """Merge `right` with its roles. `right` has to be a dictionary.
        """
        right = right_from_dict(info)
        for role_name in list(right.roles):
            role = self.roles[role_name]
            right.merge(role)

        return right

    def right(self, token):
        try:
            right = self.rights[token]
        except KeyError:
            # if guest role exists, use it
            if self.guest and self.guest in self.roles:
                return self.roles[self.guest]
            else:
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

            if right.is_allowed(cube_name, self.allow_after_denied):
                authorized.append(cube)

        return authorized

    def restricted_cell(self, identity, cube, cell):
        right = self.right(identity)

        cuts = right.cell_restrictions.get(cube.name)

        # Append cuts for "any cube"
        any_cuts = right.cell_restrictions.get(ALL_CUBES_WILDCARD, [])
        if any_cuts:
            cuts += any_cuts

        if cuts:
            restriction_cuts = []
            for cut in cuts:
                if isinstance(cut, compat.string_type):
                    cut = cut_from_string(cut, cube)
                else:
                    cut = cut_from_dict(cut)
                cut.hidden = True
                restriction_cuts.append(cut)

            restriction = Cell(cube, restriction_cuts)
        else:
            restriction = Cell(cube)

        ident_dim = None
        if self.identity_dimension:
            try:
                ident_dim = cube.dimension(self.identity_dimension)
            except NoSuchDimensionError:
                # If cube has the dimension, then use it, otherwise just
                # ignore it
                pass

        if ident_dim:
            hier = ident_dim.hierarchy(self.identity_hierarchy)

            if len(hier) != 1:
                raise ConfigurationError("Identity hierarchy has to be flat "
                                         "(%s in dimension %s is not)"
                                         % (str(hier), str(ident_dim)))

            # TODO: set as hidden
            cut = PointCut(ident_dim, [identity], hierarchy=hier, hidden=True)
            restriction = restriction & Cell(cube, [cut])

        if cell:
            return cell & restriction
        else:
            return restriction

    def hierarchy_limits(self, token, cube):
        right = self.right(token)

        return right.hierarchy_limits.get(str(cube), [])


