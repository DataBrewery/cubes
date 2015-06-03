# -*- coding: utf-8 -*-
from ..errors import *
from flask import Response, redirect
import re

__all__ = (
    "Authenticator",
    "NotAuthenticated"
)

# IMPORTANT: This is provisional code. Might be changed or removed.
#

class NotAuthenticated(Exception):
    pass


class Authenticator(object):
    def authenticate(self, request):
        raise NotImplementedError

    def info_dict(self, request):
        return { 'username' : self.authenticate(request) }

    def logout(self, request, identity):
        return "logged out"


class AbstractBasicAuthenticator(Authenticator):
    def __init__(self, realm=None):
        self.realm = realm or "Default"
        self.pattern = re.compile(r"^(http(?:s?)://)([^/]+.*)$", re.IGNORECASE)

    def logout(self, request, identity):
        headers = {"WWW-Authenticate": 'Basic realm="%s"' % self.realm}
        url_root = request.args.get('url', request.url_root)
        m = self.pattern.search(url_root)
        if m:
            url_root = m.group(1) + "__logout__@" + m.group(2)
            return redirect(url_root, code=302)
        else:
            return Response("logged out", status=401, headers=headers)

class AdminAdminAuthenticator(AbstractBasicAuthenticator):
    """Simple HTTP Basic authenticator for testing purposes. User name and
    password have to be the same. User name is passed as the authenticated
    identity."""
    def __init__(self, realm=None, **options):
        super(AdminAdminAuthenticator, self).__init__(realm=realm)

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


class HTTPBasicProxyAuthenticator(AbstractBasicAuthenticator):
    def __init__(self, realm=None, **options):
        super(HTTPBasicProxyAuthenticator, self).__init__(realm=realm)
        self.realm = realm or "Default"
        self.pattern = re.compile(r"^(http(?:s?)://)([^/]+.*)$", re.IGNORECASE)

    def authenticate(self, request):
        """Permissive authenticator using HTTP Basic authentication that
        assumes the server to be behind a proxy, and that the proxy authenticated the user. 
        Does not check for a password, just passes the `username` as identity"""
        auth = request.authorization

        if auth:
            return auth.username

        raise NotAuthenticated(realm=self.realm)

