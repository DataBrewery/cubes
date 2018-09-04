# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import unittest

from cubes_lite.compat import py3k
if not py3k:
    unittest.TestCase.assertRaisesRegex = unittest.TestCase.assertRaisesRegexp

from . import sql
