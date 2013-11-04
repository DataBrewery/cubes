# -*- coding=utf -*-
from ..extensions import get_namespace, initialize_namespace
from ..errors import *
from flask import Response

__all__ = (
    "Authenticator",
    "NotAuthenticated"
)

# IMPORTANT: This is provisional code. Might be changed or removed.
#

class NotAuthenticated(Exception):
    pass


def create_authenticator(name, **options):
    """Gets a new instance of an authorizer with name `name`."""

    ns = get_namespace("slicer_authenticators")
    if not ns:
        ns = initialize_namespace("slicer_authenticators",
                                  root_class=Authenticator,
                                  suffix="_authenticator",
                                  option_checking=True)

    try:
        factory = ns[name]
    except KeyError:
        raise ConfigurationError("Unknown authenticator '%s'" % name)

    return factory(**options)


class Authenticator(object):
    def authenticate(self, request):
        raise NotImplementedError

    def logout(self, request, identity):
        return "logged out"


class AdminAdminAuthenticator(Authenticator):
    """Simple HTTP Basic authenticator for testing purposes. User name and
    password have to be the same. User name is passed as the authenticated
    identity."""
    def authenticate(self, request):
        auth = request.authorization
        if auth and auth.username == auth.password:
            return auth.username
        else:
            raise NotAuthenticated

        raise NotAuthenticated


class PassParameterAuthenticator(Authenticator):
    """Permissive authenticator that passes an URL parameter (default
    ``api_key``) as idenity."""
    def __init__(self, parameter=None, **options):
        super(PassParameterAuthenticator, self).__init__(**options)
        self.parameter_name = parameter or "api_key"

    def authenticate(self, request):
        return request.args.get(self.parameter_name)


class HTTPBasicProxyAuthenticator(Authenticator):
    def __init__(self, realm=None, **options):
        super(HTTPBasicProxyAuthenticator, self).__init__(**options)
        self.realm = realm or "Default"

    def authenticate(self, request):
        """Permissive authenticator using HTTP Basic authentication that
        assumes the server to be behind a proxy, and that the proxy authenticated the user. 
        Does not check for a password, just passes the `username` as identity"""
        auth = request.authorization

        if auth:
            return auth.username

        raise NotAuthenticated(realm=self.realm)

    def logout(self, request, identity):
        headers = {"WWW-Authenticate": 'Basic realm="%s"' % self.realm}
        response = Response("logged out", status=401, headers=headers)
        return response
