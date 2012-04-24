"""Cubes SQL backend utilities"""
from sqlalchemy import create_engine, Table, Column, Integer, String, Float, MetaData, ForeignKey
from StringIO import StringIO

def ddl_for_model(url, model, fact_prefix=None, dimension_prefix=None):
    """Create a star schema DDL for a model.
    
    Parameters:
    
    * `url` - database url – no connection will be created, just used by 
       SQLAlchemy to determine appropriate engine backend
    * `cube` - cube to be described
    * `dimension_prefix` - prefix used for dimension tables
    
    As model has no data storage type information, following simple rule is
    used:
    
    * fact ID is an integer
    * all keys are strings
    * all attributes are strings
    * all measures are floats
    
    .. warning::
    
        Does not respect localized models yet.
    
    """
    dim_tables = {}
    dim_keys = {}
    
    out = StringIO()

    dimension_prefix = dimension_prefix or ""
    fact_prefix = fact_prefix or ""
    def dump(sql, *multiparams, **params):
        out.write(('%s' %
            sql.compile(dialect=engine.dialect)).strip()+';\n/\n')

    engine = create_engine(url, strategy='mock', executor=dump)

    metadata = MetaData(engine)

    # Create dimension tables
    
    for dim in model.dimensions:
        # If the dimension is represented by one field only, then there is
        # no need to create a separate table.
        if dim.is_flat and not dim.has_details:
            continue
        
        # Create and store constructed table name and key identifier. They
        # will be used in fact table creation
        
        name = dimension_prefix+dim.name
        dim_tables[dim.name] = name
        dim_key = dim.name + "_key"
        dim_keys[dim.name] = dim_key

        table = Table(name, metadata)
        table.append_column(Column(dim_key, Integer, primary_key=True))
        for attr in dim.all_attributes():
            table.append_column(Column(attr.name, String))
        
    # Create fact tables

    for cube in model.cubes.values():

        table = Table(fact_prefix+cube.name, metadata)
        table.append_column(Column(attr.name, Integer))

        for dim in cube.dimensions:
            if dim.is_flat and not dim.has_details:
                col = Column(dim.name, String)
            else:
                fkey = "%s.%s" % (dim_tables[dim.name], dim_keys[dim.name])
                col = Column(dim_keys[dim.name], Integer, ForeignKey(fkey), nullable=False)
            table.append_column(col)
    
        for attr in cube.measures:
            table.append_column(Column(attr.name, Float))
    
    metadata.create_all()
    
    return out.getvalue()

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