# -*- coding=utf -*-

from ...mapper import Mapper
from ...errors import *

__all__ = (
    "MixpanelMapper",
)

def _mangle_dimension_name(name):
    """Return a dimension name from a mixpanel property name."""
    fixed_name = name.replace("$", "_")
    fixed_name = fixed_name.replace(" ", "_")

    return fixed_name

def cube_event_key(cube):
    """Returns key used for cube"""
    return "cube:%s" % cube

class MixpanelMapper(Mapper):
    def __init__(self, cube, locale=None, property_dimensions=None, **options):
        """Create a Mixpanel attribute mapper"""
        super(MixpanelMapper, self).__init__(cube, locale, **options)

        self.property_to_dimension = {}

        for dim_name in property_dimensions:
            try:
                prop = self.mappings[dim_name]
            except KeyError:
                pass
            else:
                self.property_to_dimension[prop] = dim_name

        self.event_name = self.mappings.get(cube_event_key(cube.name),
                                            cube.name)

    def physical(self, attr):
        phys = super(MixpanelMapper, self).physical(attr)
        if phys is None:
            return attr.ref()

    def logical_from_physical(self, physical):
        try:
            logical = self.property_to_dimension[physical]
        except KeyError:
            logical = _mangle_dimension_name(physical)

        return logical

