# -*- coding: utf-8 -*-
# Data preparation for the hello_world example
from __future__ import print_function

from sqlalchemy import create_engine
from cubes.tutorial.sql import create_table_from_csv
from pathlib import Path


cur_folder = Path(__file__).parent
csv_path = cur_folder / 'data.csv'
sqlite_path = cur_folder / 'data.sqlite'

# 1. Prepare SQL data in memory

FACT_TABLE = "irbd_balance"

print("preparing data...")

engine = create_engine(f'sqlite:///{sqlite_path}')

create_table_from_csv(engine,
                      str(csv_path),
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
