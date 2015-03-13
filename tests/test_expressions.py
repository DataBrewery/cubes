# -*- encoding=utf -*-
from __future__ import absolute_import

import unittest

from cubes import create_attribute
from cubes.errors import ExpressionError
from cubes.expressions import sorted_attributes


class ExpressionUnitTestCase(unittest.TestCase):
    def setUp(self):
        attrs = [
            {"name": "a"},
            {"name": "b", "expression": "a + 1"},
            {"name": "c", "expression": "b + 1"},
            {"name": "d", "expression": "10"},
            {"name": "e", "expression": "unknown"},
            {"name": "loop1", "expression": "loop2 + 1"},
            {"name": "loop2", "expression": "loop1 + 1"},
            {"name": "indirect_loop1", "expression": "intermediate"},
            {"name": "intermediate", "expression": "indirect_loop1"},
            {"name": "indirect_loop2", "expression": "indirect_loop1"},
        ]

        self.attrs = {attr["name"]:create_attribute(attr) for attr in attrs}

    def attributes(self, *attrs):
        return [self.attrs[attr] for attr in attrs]

    def test_sorted_attributes_base(self):
        """Sorted attributes - basic sanity checks"""
        attrs = sorted_attributes(self.attributes())
        self.assertListEqual(attrs, [])

        attrs = sorted_attributes(self.attributes("a"))
        self.assertListEqual(attrs, self.attributes("a"))

    def test_sorted_attributes(self):
        attrs = sorted_attributes(self.attributes("c", "b", "a"))
        self.assertListEqual(attrs, self.attributes("a", "b", "c"))

    def test_sorted_unknown(self):
        with self.assertRaisesRegex(ExpressionError, "Unknown"):
            attrs = sorted_attributes(self.attributes("c", "b"))

    def test_sorted_circular(self):
        with self.assertRaisesRegex(ExpressionError, "Circular"):
            sorted_attributes(self.attributes("loop1", "loop2"))

        with self.assertRaisesRegex(ExpressionError, "Circular"):
            sorted_attributes(self.attributes("indirect_loop1",
                                              "intermediate",
                                              "indirect_loop2"))
