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

        **Limitations:**
        
        * only one locale can be used for browsing at a time
        * locale is implemented as denormalized: one column for each language

        """
        super(StarBrowser, self).__init__()
        self.cube = cube
        self.simplify_dimension_references = True
        
    def split_reference_string(self, string):
        """Split reference string to attribute and dimension"""
        pass
    
    def logical_reference(self, dimension, attribute):
        """Returns logical reference as string for `attribute` in `dimension`. 
        If `dimension` is ``Null`` then fact table is assumed. The logical reference might have
        following forms:

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

    def physical_reference(self, logical_reference, locale = None):
        """Returns physical reference as tuple for `logical_reference`. 
        If there is no dimension in logical reference, then fact table is 
        assumed. The returned tuple has structure: (table, column).

        The algorithm to find physicl reference is as follows::
        
            create logical reference string

            IF there is mapping for the logical reference:
                use the mapped value as physical reference

            ELSE:

                IF dimension specified:
                    table name is dimension name
                    IF there is dimension table prefix, THEN use the prefix for table name
                    column name is attribute name

                ELSE (if no dimension is specified):
                    table name is fact table name
                    
                IF locale is specified:
                    append '_' and locale to the column name
        """

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
