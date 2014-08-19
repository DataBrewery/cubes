import unittest
from cubes.workspace import Namespace
from .common import CubesTestCaseBase

class NamespaceTestCase(CubesTestCaseBase):
    def test_create(self):
        ns = Namespace()
        ns.create_namespace("slicer")
        self.assertIn("slicer", ns.namespaces)
        self.assertIsInstance(ns.namespaces["slicer"], Namespace)

    def test_get_namespace(self):
        base = Namespace()
        slicerns = base.create_namespace("slicer")

        self.assertEqual((base, []), base.namespace(""))
        self.assertEqual((slicerns, []), base.namespace("slicer"))
        self.assertEqual((base, ["unknown"]), base.namespace("unknown"))
        self.assertEqual((base, ["one", "two"]), base.namespace("one.two"))

    def test_get_namespace_create(self):
        base = Namespace()
        slicerns = base.create_namespace("slicer")

        self.assertEqual((base, []), base.namespace("", create=True))
        self.assertEqual((slicerns, []), base.namespace("slicer", create=True))

        (ns, remainder) = base.namespace("new", create=True)
        self.assertEqual([], remainder)
        self.assertEqual((ns, []), base.namespace("new"))

        (last, remainder) = base.namespace("one.two.three", create=True)
        self.assertEqual([], remainder)

        self.assertIn("one", base.namespaces)
        (ns, remainder) = base.namespace("one")
        self.assertEqual([], remainder)

        self.assertIn("two", ns.namespaces)
        (ns, remainder) = ns.namespace("two")
        self.assertEqual([], remainder)

        self.assertIn("three", ns.namespaces)
        (ns, remainder) = ns.namespace("three")
        self.assertEqual([], remainder)

        (last, remainder) = base.namespace("one.two.three.four.five")
        self.assertEqual(["four", "five"], remainder)

    def test_find_cube(self):
        base = Namespace()

        (ns, nsname, basename) = base.find_cube("cube")
        self.assertEqual(ns, base)
        self.assertEqual(nsname, "")
        self.assertEqual(basename, "cube")

        (ns, nsname, basename) = base.find_cube("extern.cube")
        self.assertEqual(ns, base)
        self.assertEqual(nsname, "")
        self.assertEqual(basename, "extern.cube")

        (ns, nsname, basename) = base.find_cube("even.deeper.extern.cube")
        self.assertEqual(ns, base)
        self.assertEqual(nsname, "")
        self.assertEqual(basename, "even.deeper.extern.cube")

        extern = base.create_namespace("extern")
        (ns, nsname, basename) = base.find_cube("extern.cube")
        self.assertEqual(ns, extern)
        self.assertEqual(nsname, "")
        self.assertEqual(basename, "cube")

        (ns, nsname, basename) = base.find_cube("extern.deeper.cube")
        self.assertEqual(ns, extern)
        self.assertEqual(nsname, 'extern')
        self.assertEqual(basename, "deeper.cube")

        (deep, remainder) = base.namespace("even.deeper.extern", create=True)
        (ns, nsname, basename) = base.find_cube("even.deeper.extern.cube")
        self.assertEqual(ns, deep)
        self.assertEqual(nsname, "")
        self.assertEqual(basename, "cube")
