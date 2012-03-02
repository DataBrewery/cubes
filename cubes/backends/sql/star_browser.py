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

class StarBrowser(object):
    """docstring for StarBrowser"""
    
    def __init__(self, cube):
        """StarBrowser is a SQL-based AggregationBrowser implementation that 
        can aggregate star and snowflake schemas without need of having 
        explicit view or physical denormalized table.

        Attributes:
        
        * `cube` - browsed cube
        * `simplify_dimension_references` – references for flat dimensions 
          (with one level and no details) will be just dimension names, no 
          attribute name. Might be useful when using single-table schema, for 
          example, with couple of one-column dimensions.

        .. warning:
            
            Not fully implemented yet.

        """
        super(StarBrowser, self).__init__()
        self.cube = cube
        self.simplify_dimension_references = True
        
    def logical_reference(self, attribute, dimension = None, locale = None):
        """Returns logical reference as string for `attribute` in `dimension`. 
        If `dimension` is ``Null`` then fact table is assumed. The logical reference might have
        following forms:

        * ``dimension.attribute`` - dimension attribute
        * ``dimension.attribute.locale`` - localized dimension attribute
        * ``attribute`` - fact measure or detail
        * ``attribute.locale`` - localized fact measure or detail
        
        If `simplify_dimension_references` is ``True`` then references for flat 
        dimensios without details look like:

        * ``dimension``
        * ``dimension.locale``
        """

        if self.simplify_dimension_references and (dimension.is_flat and not dimension.has_details):
            logical_name = field_name
        else:
            logical_name = dimension.name + '.' + field_name
        
        if dimension:
            alias = str(dimension) + "." + str(attribute)
        else:
            alias = str(attribute)
        
        if locale:
            reference = alias + "." + locale
        else:
            reference = alias
            
        return reference

    def physical_reference(self, attribute, dimension = None, locale = None):
        """Returns physical reference as tuple for `attribute` in `dimension`. 
        If `dimension` is ``Null`` then fact table is assumed. The returned tuple
        has structure: (table, column).
        
        The algorithm to find physicl reference is as follows::
        
            create logical reference string
            IF there is mapping for the logical reference:
                use the mapped value as physical reference
            ELSE:
                IF dimension specified:
                    table name is dimension name
                    if there is dimension table prefix, then use the prefix for table name
                    column name is attribute name
                ELSE (if no dimension is specified):
                    table name is fact table name
                IF locale is specified:
                    append '_' and locale to the column name
        * 
        
        """

        logical_reference = self.logical_reference(attribute, dimension, locale)

        if logical_reference in self.mappings:
            reference = self.mappings[logical_reference]
        else:
            if dimension:
                table_name = str(dimension)
                if self.dimension_table_prefix:
                    table_name = self.dimension_table_prefix + table_name
            else:
                table_name = self.fact_name

            column_name = str(attribute)

            if locale:
                column_name = column_name + "_" + locale
            reference = (table_name, column_name)
            
        return reference


    def aggregate(self, cell, measures = None, drilldown = None, details = False, **options):
        pass
