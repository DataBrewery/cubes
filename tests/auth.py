# -*- coding=utf -*-
import unittest
from cubes import *
from .common import CubesTestCaseBase

from json import dumps

def printable(obj):
    return dumps(obj, indent=4)

class AuthTestCase(CubesTestCaseBase):
    def test_empty(self):
        self.auth = SimpleAuthorizer()
        with self.assertRaises(NotAuthorized):
            self.auth.authorize("john", "sales")
