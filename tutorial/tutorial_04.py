import sqlalchemy
import cubes
import cubes.tutorial.sql as tutorial
import logging
import copy
        
# In this tutorial you are going to learn how to run and use Slicer OLAP server
#
# The file is only for database initialization
#
# Run this script:
#      python tutorial_04.py
# Run slicer server:
#      slicer serve tutorial_04.py
#
# Query the server:
#      curl http://localhost:5000/aggregate


# 1. Prepare SQL data in memory

logger = logging.getLogger("cubes")
logger.setLevel(logging.WARN)

FACT_TABLE = "ft_irbd_balance"
FACT_VIEW = "vft_irbd_balance"

engine = sqlalchemy.create_engine('sqlite:///tutorial.sqlite')
tutorial.create_table_from_csv(engine, 
                      "data/IBRD_Balance_Sheet__FY2010-t03.csv", 
                      table_name=FACT_TABLE, 
                      fields=[
                            ("category", "string"),
                            ("category_label", "string"), 
                            ("subcategory", "string"), 
                            ("subcategory_label", "string"), 
                            ("line_item", "string"),
                            ("year", "integer"), 
                            ("amount", "integer")],
                      create_id=True    
                        
                        )

model = cubes.load_model("models/model_04.json")

cube = model.cube("irbd_balance")
cube.fact = FACT_TABLE

# 4. Create a browser and get a cell representing the whole cube (all data)

connection = engine.connect()
dn = cubes.backends.sql.SQLDenormalizer(cube, connection)

dn.create_view(FACT_VIEW)
