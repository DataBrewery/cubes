# -*- coding=utf -*-
"""
    cubes.datastructures
    ~~~~~~~~~~~~~~~~~~~~~

    Utility data structures.
"""


from typing import (
    Generic,
    Mapping,
    TypeVar
)

__all__ = [
    "AttributeDict",
]


T = TypeVar("T")

#
# Credits:
# Originally from the Celery project:  http://www.celeryproject.org
#
class AttributeDict(dict, Generic[T]):
    """Augment classes with a Mapping interface by adding attribute access.

    I.e. `d.key -> d[key]`.

    """

    def __getattr__(self, key: str) -> T:
        """`d.key -> d[key]`"""
        try:
            return self[key]
        except KeyError:
            raise AttributeError(
                '{0!r} object has no attribute {1!r}'.format(
                    type(self).__name__, key))

    def __setattr__(self, key: str, value: T) -> None:
        """`d[key] = value -> d.key = value`"""
        self[key] = value

