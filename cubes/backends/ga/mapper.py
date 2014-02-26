# -*- coding=utf -*-

from ...mapper import Mapper
from ...errors import *

__all__ = (
    "GoogleAnalyticsMapper",
    "ga_id_to_identifier"
)

def ga_id_to_identifier(ga_id):
    """Convert GA attribute/object ID to identifier."""
    if ga_id.startswith("ga:"):
        return ga_id[3:]
    else:
        raise InternalInconsistencyError("Unexpected GA attribute name"
                                         % ga_id)

class GoogleAnalyticsMapper(Mapper):
    def __init__(self, cube, locale=None, **options):
        super(GoogleAnalyticsMapper, self).__init__(cube, locale, **options)
        # ... other initialization here ...
        self.mappings = cube.mappings or {}

    def physical(self, attribute, locale=None):
        # See also: ga_id_to_identifier
        logical = self.logical(attribute, locale)

        if logical in self.mappings:
            return self.mappings[logical]
        else:
            return "ga:" + attribute.name
