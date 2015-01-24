# -*- encoding: utf-8 -*-
#
# IMPORTANT: Analogous to the starschema.py, don't put any Cubes specific
# objects into this test case
#

from __future__ import absolute_import

import unittest

class StarSchemaTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_basic(self):
        """Test denormalized table selection of few columns"""

    def test_join(self):
        """Test single join, two joins"""

    def test_join_alias(self):
        """Test single aliased join, test two joins on same table, one aliased
        """

    def test_join_order(self):
        """Test that the order of joins does not matter"""

    def test_relevant_join(self):
        """Test that only tables containing required attributes are being
        joined"""

    def test_join_method_detail(self):
        """Test 'detail' join method"""

    def test_join_method_master(self):
        """Test 'detail' join master"""

    def test_extract(self):
        """Test that mapping.extract works"""

    def test_unary(self):
        """Test that mapping.unary works"""

    def test_statement_table(self):
        """Test using a statement as a table"""

