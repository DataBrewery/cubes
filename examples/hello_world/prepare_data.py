# -*- coding: utf-8 -*-
# Data preparation for the hello_world example
from __future__ import print_function

from sqlalchemy import create_engine
from cubes.tutorial.sql import create_table_from_csv

# 1. Prepare SQL data in memory

FACT_TABLE = "irbd_balance"

print("preparing data...")

engine = create_engine('sqlite:///data.sqlite')

create_table_from_csv(engine,
                      "data.csv",
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

print("done. file data.sqlite created")
