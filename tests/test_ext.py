import unittest

from typing import Dict

from cubes.ext import Extensible, Parameter
from cubes.errors import ConfigurationError


class StoreBase(Extensible, abstract=True):
    __extension_type__ = "store"
    def value(self) -> int:
        raise NotImplementedError


class MyStore(StoreBase, name="my"):

    __parameters__ = [
        Parameter("number", "integer")
    ]

    number: int

    def __init__(self, number: int):
        self.number = number

    def value(self) -> int:
        return self.number


class ExtensibleTestCase(unittest.TestCase):
    def test_basic(self) -> None:
        obj: StoreBase
        obj = StoreBase.concrete_extension("my")(1)
        self.assertEqual(obj.value(), 1)

    def test_params(self) -> None:
        obj: StoreBase
        params: Dict[str, str]
        params = {"number": "2"}

        obj = StoreBase.concrete_extension("my").create_with_params(params)
        self.assertEqual(obj.value(), 2)

    def test_invalid_param_type(self) -> None:
        obj: StoreBase
        params: Dict[str, str]
        params = {"number": "something"}

        with self.assertRaises(ConfigurationError):
            obj = StoreBase.concrete_extension("my").create_with_params(params)

    def test_invalid_param(self) -> None:
        obj: StoreBase
        params: Dict[str, str]
        params = {"somethingelse": "something"}

        with self.assertRaises(ConfigurationError):
            obj = StoreBase.concrete_extension("my").create_with_params(params)