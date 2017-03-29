import unittest

from cubes.metadata.physical import Join, JoinKey
from cubes.errors import ArgumentError

class SchemaUtilitiesTestCase(unittest.TestCase):
    """Test independent utility functions and structures."""

    def test_to_join_key(self):
        """Test basic structure conversions."""

        key = JoinKey.from_dict("col")
        self.assertEqual(JoinKey(schema=None, table=None, columns=["col"]), key)

        key = JoinKey.from_dict("table.col")
        self.assertEqual(JoinKey(table="table", columns=["col"]), key)

        key = JoinKey.from_dict("schema.table.col")
        self.assertEqual(JoinKey(columns=["col"], table="table", schema="schema"), key)

        key = JoinKey.from_dict({"column": "col"})
        self.assertEqual(JoinKey(columns=["col"], table=None, schema=None), key)

        key = JoinKey.from_dict({"table":"table", "column": "col"})
        self.assertEqual(JoinKey(columns=["col"], table="table", schema=None), key)

        key = JoinKey.from_dict({"schema":"schema",
                                 "table":"table",
                                 "column": "col"})

        self.assertEqual(JoinKey(columns=["col"], table="table", schema="schema"), key)

        # Test exceptions
        #

        with self.assertRaises(ValueError):
            JoinKey.from_dict([])

        with self.assertRaises(ValueError):
            JoinKey.from_dict(["a", "b", "c"])

        with self.assertRaises(ValueError):
            JoinKey.from_dict(["one", "two", "three", "four"])

        with self.assertRaises(ValueError):
            JoinKey.from_dict("one.two.three.four")

    @unittest.skip("Should be Join.from_dict()")
    def test_to_join(self):
        join = ("left", "right")
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             None,
                                             None))

        join = ("left", "right", "alias")
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             None))

        join = ("left", "right", "alias", "match")
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             "match"))

        # Dict
        join = {"master": "left", "detail": "right"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             None,
                                             None))

        join = {"master": "left", "detail": "right", "alias": "alias"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             None))

        join = {"master": "left", "detail": "right", "method": "match"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             None,
                                             "match"))

        join = {"master": "left", "detail": "right", "alias": "alias",
                "method": "match"}
        self.assertEqual(to_join(join), Join(to_join_key("left"),
                                             to_join_key("right"),
                                             "alias",
                                             "match"))

        # Error
        with self.assertRaises(ArgumentError):
            to_join(["left", "right", "detail", "master", "something"])

        # Error
        with self.assertRaises(ArgumentError):
            to_join(["onlyone"])


