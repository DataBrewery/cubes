# -*- coding=utf -*-
from ..extensions import get_namespace, initialize_namespace
from ..errors import *

# IMPORTANT: This is provisional code. Might be changed or removed.
#

class NotAuthenticated(Exception):
    pass


def create_authenticator(name, **options):
    """Gets a new instance of an authorizer with name `name`."""

    ns = get_namespace("slicer_authenticators")
    if not ns:
        ns = initialize_namespace("slicer_authenticators",
                                  root_class=SlicerAuthenticator,
                                  suffix="_authenticator",
                                  option_checking=True)

    try:
        factory = ns[name]
    except KeyError:
        raise ConfigurationError("Unknown authenticator '%s'" % name)

    return factory(**options)


class SlicerAuthenticator(object):
    def authenticate(self, request):
        raise NotImplementedError


class AdminAdminAuthenticator(SlicerAuthenticator):
    """Simple HTTP Basic authenticator for testing purposes. User name and
    password have to be the same. User name is passed as the authenticated
    identity."""

    def authenticate(self, request):
        auth = request.authorization
        if auth:
            if auth.username == auth.password:
                return auth.username
            else:
                raise NotAuthenticated
        raise NotAuthenticated


class BasicHTTPAuthenticator(SlicerAuthenticator):
    def authenticate(self, request):
        auth = request.authorization
        print "=== AUTH RECEIVED: ", auth
        if auth:
            return auth.username

        raise NotAuthenticated

