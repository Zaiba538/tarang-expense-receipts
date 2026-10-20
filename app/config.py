"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

APP_NAME = os.getenv("APP_NAME", "Tarang Pharma Expense Receipt Review")
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "en")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
UPLOAD_DIR = ROOT_DIR / "uploads"
REPORT_DIR = ROOT_DIR / "reports"
DATA_DIR = ROOT_DIR / "data" / "Task 2 Files"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
