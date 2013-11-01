# -*- coding=utf -*-
from flask import Blueprint, Flask, Response, request, g, current_app
from functools import wraps

import ConfigParser
from ..workspace import Workspace
from ..auth import NotAuthorized
from ..browser import Cell, cuts_from_string, SPLIT_DIMENSION_NAME
from ..errors import *
from .utils import *
from .errors import *
from .local import *
from ..calendar import CalendarMemberConverter

# Utils
# -----

def prepare_cell(argname="cut", target="cell"):
    """Sets `g.cell` with a `Cell` object from argument with name `argname`"""
    # Used by prepare_browser_request and in /aggregate for the split cell


    # TODO: experimental code, for now only for dims with time role
    converters = {
        "time": CalendarMemberConverter(workspace.calendar)
    }

    cuts = []
    for cut_string in request.args.getlist(argname):
        cuts += cuts_from_string(g.cube, cut_string,
                                 role_member_converters=converters)

    if cuts:
        cell = Cell(g.cube, cuts)
    else:
        cell = None

    if workspace.authorizer:
        cell = workspace.authorizer.restricted_cell(g.auth_identity,
                                                    cube=g.cube,
                                                    cell=cell)
    setattr(g, target, cell)


def requires_cube(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        cube_name = request.view_args.get("cube_name")
        try:
            g.cube = workspace.cube(cube_name)
        except NoSuchCubeError:
            raise NotFoundError(cube_name, "cube",
                                "Unknown cube '%s'" % cube_name)

        return f(*args, **kwargs)

    return wrapper

def requires_browser(f):
    """Prepares three global variables: `g.cube`, `g.browser` and `g.cell`.
    Also athorizes the cube using `authorize()`."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        cube_name = request.view_args.get("cube_name")
        if cube_name:
            cube = workspace.cube(cube_name)
        else:
            cube = None

        g.cube = cube
        g.browser = workspace.browser(g.cube)

        prepare_cell()

        if "page" in request.args:
            try:
                g.page = int(request.args.get("page"))
            except ValueError:
                raise RequestError("'page' should be a number")
        else:
            g.page = None

        if "pagesize" in request.args:
            try:
                g.page_size = int(request.args.get("pagesize"))
            except ValueError:
                raise RequestError("'pagesize' should be a number")
        else:
            g.page_size = None

        # Collect orderings:
        # order is specified as order=<field>[:<direction>]
        #
        g.order = []
        for orders in request.args.getlist("order"):
            for order in orders.split(","):
                split = order.split(":")
                if len(split) == 1:
                    g.order.append( (order, None) )
                else:
                    g.order.append( (split[0], split[1]) )

        authorize(cube)

        return f(*args, **kwargs)

    return wrapper


# Authorization
# =============

def authorize(cube):
    """Authorizes the `cube` according to current settings and request
    parameters."""

    if not workspace.authorizer:
        return

    logger.debug("authorizing cube %s for %s"
                 % (str(cube), g.auth_identity))

    authorized = workspace.authorizer.authorize(g.auth_identity, [cube])
    if not authorized:
        raise NotAuthorizedError("Authorization of cube '%s' failed for "
                                 "'%s'" % (str(cube), g.auth_identity))

def requires_authorization(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        authorize(g.cube)
        return f(*args, **kwargs)

    return wrapper


