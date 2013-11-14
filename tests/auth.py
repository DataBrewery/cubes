# -*- coding=utf -*-
import unittest
from cubes import *
from .common import CubesTestCaseBase

from json import dumps

def printable(obj):
    return dumps(obj, indent=4)

class AuthTestCase(CubesTestCaseBase):
    def setUp(self):
        self.sales_cube = Cube("sales")
        self.churn_cube = Cube("churn")

    def test_empty(self):
        self.auth = SimpleAuthorizer()
        self.assertEqual([], self.auth.authorize("john", [self.sales_cube]))

    def test_authorize(self):
        rights = {
            "john": {"allowed_cubes": ["sales"]}
        }
        self.auth = SimpleAuthorizer(rights=rights)

        self.assertEqual([self.sales_cube],
                         self.auth.authorize("john", [self.sales_cube]))
        self.assertEqual([], self.auth.authorize("ivana", [self.churn_cube]))

    def test_deny(self):
        rights = {
            "john": {"denied_cubes": ["sales"]}
        }
        self.auth = SimpleAuthorizer(rights=rights)

        self.assertEqual([self.churn_cube], self.auth.authorize("john", [self.churn_cube]))

        self.assertEqual([],
                         self.auth.authorize("john", [self.sales_cube]))
        self.assertEqual([], self.auth.authorize("ivana", [self.churn_cube]))

    def test_role(self):
        roles = {
            "marketing": {"allowed_cubes": ["sales"]}
        }
        rights = {
            "john": {"roles": ["marketing"]}
        }
        self.auth = SimpleAuthorizer(rights=rights, roles=roles)

        self.assertEqual([self.sales_cube],
                         self.auth.authorize("john", [self.sales_cube]))

    def test_role_inheritance(self):
        roles = {
            "top": {"allowed_cubes": ["sales"]},
            "marketing": {"roles": ["top"]}
        }
        rights = {
            "john": {"roles": ["marketing"]}
        }
        self.auth = SimpleAuthorizer(rights=rights, roles=roles)

        self.assertEqual([self.sales_cube],
                         self.auth.authorize("john", [self.sales_cube]))

