# -*- coding=utf -*-

import os.path
import json

from .extensions import get_namespace, initialize_namespace
from .browser import Cell
from .errors import *

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
                                  suffix="_store",
                                  option_checking=True)

    try:
        factory = ns[name]
    except KeyError:
        raise ConfigurationError("Unknown authorizer '%s'" % name)

    return factory(**options)


class Authorizer(object):
    def cube_is_allowed(object, token):
        """Return a list of allowed cubes for authorization `token`."""
        raise NotImplementedError

    def authorize(object, token, cube, cell):
        """Returns appropriated `cell` within `cube` for authorization token
        `token`. The `token` is specific to concrete authorizer object.

        If `token` does not authorize access to the cube a NotAuthorized exception is
        raised."""
        raise NotImplementedError


class SimpleAuthorizer(Authorizer):
    __options__ = [
        {
            "name": "tokens_file",
            "description": "JSON file with authorization tokens and their "
                           "respective configuration (cubes, cells, ...).",
            "type": "string"
        },

    ]

    def __init__(self, tokens_file=None, tokens=None):
        super(SimpleAuthorizer, self).__init__(self)

        if tokens_file or tokens:
            raise ArgumentError("Both tokens_file and tokens provided, "
                                "use only one.")

        if tokens_file:
            if not os.path.exists(tokens_file):
                raise ConfigurationError("Can not find tokens file '%s'"
                                         % tokens_file)

            try:
                f = open(tokens_file)
            except IOError:
                raise ConfigurationError("Can not open tokens file '%s'"
                                         % tokens_file)

            try:
                tokens = json.load(f)
            except ValueError as e:
                raise SyntaxError("Syntax error in tokens file %s: %s"
                                  % (tokens_file, str(e)))
            finally:
                f.close()

        elif not tokens:
            raise ArgumentError("Neither tokens nor tokens_file provided")

        self.tokens = {}

        for token, info in tokens:
            self._add_token(token, info)

    def add_token(self, token, info):
        """Prepare the token's info dictionary and add it to the
        receipient."""
        info = dict(info)
        if "allow_cubes" not in info:
            info["allowed_cubes"] = []
        if "deny_cubes" not in info:
            info["deny_cubes"] = []

    def authorize(self, token, cube, cell=None):
        try:
            info = self.tokens[token]
        except KeyError:
            raise NotAuthorized("Unknown token")

        allow = info.get("allow_cubes", [])
        deny = info.get("deny_cubes")
        name = str(cube)

        if (allow and name not in allow) \
                or (deny and name in deny):
            raise NotAuthorized("Unauthorized cube '%s'" % name)

        return cell
