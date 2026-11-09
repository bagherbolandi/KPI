# -*- coding: utf-8 -*-
"""Application configuration.

For the prototype we default to SQLite so the system is fully self-contained.
For production set DATABASE_URL to a PostgreSQL DSN, e.g.
    postgresql+psycopg://kpi:secret@db:5432/kpi
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../backend
PROJECT_DIR = os.path.dirname(BASE_DIR)                                  # .../kpi-system

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'kpi.db')}")
SEED_FILE = os.path.join(PROJECT_DIR, "data", "seed_kpis.json")

SECRET_KEY = os.environ.get("KPI_SECRET_KEY", "change-me-in-production-please-0xA1B2C3")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12

# Default status thresholds (achievement ratio). Overridable per-KPI and via Settings.
DEFAULT_TH_GREEN = 0.85
DEFAULT_TH_YELLOW = 0.60

FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
