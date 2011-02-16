"""Base mongo utilities"""

def dimension_field_mapping(cube, dimension, field):
    """Return mapping for a dimension attribute. If there is no mapping defined return default mapping where
    table/dataset name is same as dimension name and column/field name is same as dimension attribute

    Return: string
    """

    reference = "%s.%s" % (dimension.name, field)
    physical = cube.mappings.get(reference)

    # If there is no mapping, use default mapping
    # FIXME: make this configurable
    if not physical:
        physical = field

    return (physical, field)

def fact_field_mapping(cube, field):
    """Return physical field name"""

    physical = cube.mappings.get(field)
    if not physical:
        physical = field

    return (physical, field)
