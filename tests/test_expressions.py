# -*- encoding=utf -*-


import unittest

from cubes import Attribute
from cubes.errors import ExpressionError
from cubes.metadata import depsort_attributes


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

        self.attrs = {attr["name"]:Attribute.from_metadata(attr) for attr in attrs}
        self.deps = {name:attr.dependencies
                     for name, attr in list(self.attrs.items())}

    def attributes(self, *attrs):
        return [self.attrs[attr] for attr in attrs]

    def test_sorted_attributes_base(self):
        """Sorted attributes - basic sanity checks"""
        attrs = depsort_attributes([], self.deps)
        self.assertListEqual(attrs, [])

        attrs = depsort_attributes(["a"], self.deps)
        self.assertListEqual(attrs, ["a"])

    def test_sorted_attributes(self):
        attrs = depsort_attributes(["c", "b", "a"], self.deps)
        self.assertListEqual(attrs, ["a", "b", "c"])

    def test_sorted_unknown(self):
        with self.assertRaisesRegex(ExpressionError, "Unknown"):
            attrs = depsort_attributes(["c", "b"], {})

    def test_sorted_circular(self):
        with self.assertRaisesRegex(ExpressionError, "Circular"):
            depsort_attributes(["loop1", "loop2"], self.deps)

        with self.assertRaisesRegex(ExpressionError, "Circular"):
            depsort_attributes(["indirect_loop1", "intermediate",
                                "indirect_loop2"], self.deps)
