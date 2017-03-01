# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import unittest
from sqlalchemy.sql.elements import True_

from cubes import SetCut, InternalError
from cubes.sql.query import QueryContext


class FakeStarSchema(object):
    label = 'test'
    fact_key_column = 'test'

    def get_star(self, *args, **kws):
        return 'test'


class ConditionsAssemblingTestCase(unittest.TestCase):
    def setUp(self):
        self.query_context = QueryContext(FakeStarSchema(), [])

    def test_deal_with_null_hierarchy_and_set_cut(self):
        self.query_context.hierarchies = {
            ('dim_org', None): ['id'],
        }
        self.query_context._columns = {
            'id': 'an_id',
        }

        cuts = [
            SetCut('dim_org', [['an_id']])
        ]

        try:
            conditions = self.query_context.conditions_for_cuts(cuts)
        except InternalError:
            self.fail('Should work with empty hierarchy')

        self.assertEqual(len(conditions), 1)

        condition = conditions[0]
        self.assertIsInstance(condition.element, True_)
