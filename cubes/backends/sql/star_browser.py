# -*- coding=utf -*-
import cubes.browser
    
# FIXME: required functionality
# 
# * number of items in drill-down
# * dimension values
# * drill-down sorting
# * drill-down pagination
# * drill-down limits (such as top-10)
# * facts sorting
# * facts pagination
# * dimension values sorting
# * dimension values pagination
# * remainder
# * ratio - aggregate sum(current)/sum(total) 
# * derived measures (should be in builder)

class AttributeMapper(object):
    """docstring for AttributeMapper"""

    def __init__(self, cube, mappings = None, locale = None):
        """Attribute mapper for a cube - maps logical references to 
        physical references (tables and columns)
        
        Attributes:
        
        * `cube` - mapped cube
        * `mappings` – dictionary containing mappings
        * `simplify_dimension_references` – references for flat dimensions 
          (with one level and no details) will be just dimension names, no 
          attribute name. Might be useful when using single-table schema, for 
          example, with couple of one-column dimensions.
        * `dimension_table_prefix` – default prefix of dimension tables, if 
          default table name is used in physical reference construction
        
        Mappings
        ++++++++
        
        Mappings is a dictionary where keys are logical attribute references
        and values are table column references. The keys are mostly in the form:
        
        * ``attribute`` for measures and fact details
        * ``attribute.locale`` for localized fact details
        * ``dimension.attribute`` for dimension attributes
        * ``dimension.attribute.locale`` for localized dimension attributes
        
        The values might be specified as strings in the form ``table.column`` 
        or as two-element arrays: [`table`, `column`].
        """
        
        super(AttributeMapper, self).__init__()

        if cube == None:
            raise Exception("Cube for mapper should not be None.")

        self.cube = cube
        self.mappings = mappings
        self.locale = locale
        
        self.simplify_dimension_references = True
        self.dimension_table_prefix = None
    
        self.collect_attributes()

    def collect_attributes(self):
        """Collect all cube attributes and create a dictionary where keys are 
        logical references and values are `cubes.model.Attribute` objects.
        This method should be used after each cube or mappings change.
        """

        self.attributes = {}
        
        for attr in self.cube.measures:
            self.attributes[self.logical(None, attr)] = (None, attr)

        for attr in self.cube.details:
            self.attributes[self.logical(None, attr)] = (None, attr)

        for dim in self.cube.dimensions:
            for level in dim.levels:
                for attr in level.attributes:
                    ref = self.logical(dim, attr)
                    self.attributes[ref] = (dim, attr)

    def logical(self, dimension, attribute):
        """Returns logical reference as string for `attribute` in `dimension`. 
        If `dimension` is ``Null`` then fact table is assumed. The logical 
        reference might have following forms:


        * ``dimension.attribute`` - dimension attribute
        * ``attribute`` - fact measure or detail
        
        If `simplify_dimension_references` is ``True`` then references for flat 
        dimensios without details is ``dimension``
        """

        if dimension:
            if self.simplify_dimension_references and \
                               (dimension.is_flat and not dimension.has_details):
                reference = dimension.name
            else:
                reference = dimension.name + '.' + str(attribute)
        else:
            reference = str(attribute)
            
        return reference

    def split_logical(self, reference):
        """Returns tuple (`dimension`, `attribute`) from `logical_reference` string. Syntax
        of the string is: ``dimensions.attribute``."""
        
        split = reference.split(".")

        if len(split) > 1:
            dim_name = split[0]
            attr_name = ".".join(split[1:])
            return (dim_name, attr_name)
        else:
            return (None, reference)

    def split_physical(self, reference, default_table = None):
        """Returns tuple (`table`, `column`) from `reference` string. 
        Syntax of the string is: ``dimensions.attribute``. Note: this method 
        works currently the same as :meth:`split_logical`. If no table is 
        specified in reference and `default_table` is not ``None``, then 
        `default_table` will be used."""

        ref = self.split_logical_reference(reference)
        return (ref[0] or default_table, ref[1])
        
    def physical(self, dimension, attribute, locale = None):
        """Returns physical reference as tuple for `logical_reference`. 
        If there is no dimension in logical reference, then fact table is 
        assumed. The returned tuple has structure: (table, column).

        The algorithm to find physicl reference is as follows::
        
            IF localization is requested:
                IF is attribute is localizable:
                    IF requested locale is one of attribute locales
                        USE requested locale
                    ELSE
                        USE default attribute locale
                ELSE
                    do not localize

            IF mappings exist:
                GET string for logical reference
                IF locale:
                    append '.' and locale to the logical reference

                IF mapping value exists for localized logical reference
                    USE value as reference

            IF no mappings OR no mapping was found:
                column name is attribute name

                IF locale:
                    append '_' and locale to the column name

                IF dimension specified:
                    # Example: 'date.year' -> 'date.year'
                    table name is dimension name

                    IF there is dimension table prefix
                        use the prefix for table name

                ELSE (if no dimension is specified):
                    # Example: 'date' -> 'fact.date'
                    table name is fact table name
        """
        
        reference = None

        # Fix locale: if attribute is not localized, use none, if it is
        # localized, then use specified if exists otherwise use default
        # locale of the attribute (first one specified in the list)

        try:
            if attribute.locales:
                locale = locale if locale in attribute.locales \
                                    else attribute.locales[0]
            else:
                locale = None
        except:
            locale = None

        # Try to get mapping if exists

        if self.cube.mappings:
            logical = self.logical(dimension, attribute)

            # Append locale to the logical reference

            if locale:
                logical += "." + locale

            # TODO: should default to non-localized reference if no mapping 
            # was found?

            reference = self.cube.mappings.get(logical)

            # Split the reference
            if isinstance(reference, basestring):
                reference = self.split_physical(reference, self.cube.fact or self.cube.name)

        # No mappings exist or no mapping was found - we are going to create
        # default physical reference
        
        if not reference:

            column_name = str(attribute)

            if locale:
                column_name += "_" + locale
            
            if dimension and not (self.simplify_dimension_references \
                                   and (dimension.is_flat 
                                        and not dimension.has_details)):
                table_name = str(dimension)

                if self.dimension_table_prefix:
                    table_name = self.dimension_table_prefix + table_name
            else:
                table_name = self.cube.fact or self.cube.name

            reference = (table_name, column_name)

        return reference

class StarBrowser(object):
    """docstring for StarBrowser"""
    
    def __init__(self, cube, locale = None):
        """StarBrowser is a SQL-based AggregationBrowser implementation that 
        can aggregate star and snowflake schemas without need of having 
        explicit view or physical denormalized table.

        Attributes:
        
        * `cube` - browsed cube

        .. warning:
            
            Not fully implemented yet.

        **Limitations:**
        
        * only one locale can be used for browsing at a time
        * locale is implemented as denormalized: one column for each language

        """
        super(StarBrowser, self).__init__()

        if cube == None:
            raise Exception("Cube for browser should not be None.")
            
        self.cube = cube
        self.mapper = AttributeMapper(cube, cube.mappings, locale)
        
    def aggregate(self, cell, measures = None, drilldown = None, details = False, **options):
        pass
