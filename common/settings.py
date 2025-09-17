from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

FOOD_COST_TARGET_PCT = float(os.getenv("FOOD_COST_TARGET_PCT", "35"))
DB_PATH = os.getenv("DB_PATH", "./dreo.db")
