"""Cubes SQL backend utilities, mostly to be used by the slicer command."""

def validate_physical_schema(url, model, fact_prefix=None, dimension_prefix=None):
    """Validate the model and mappings against physical schema - check for 
    existence of each column."""
    
    pass

def denormalize_locale(connection, localized, dernomralized, locales):
    """Create denormalized version of localized table. (not imlpemented, just proposal)

    Type 1:

    Localized table: id, locale, field1, field2, ...

    Denomralized table: id, field1_loc1, field1_loc2, field2_loc1, field2_loc2,...

    Type 2:

    Localized table: id, locale, key, field, content

    Denomralized table: id, field1_loc1, field1_loc2, field2_loc1, field2_loc2,...


    """
    pass