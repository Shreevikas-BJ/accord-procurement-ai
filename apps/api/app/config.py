import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + str(ROOT / "data" / "local.db"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STORAGE_PATH = Path(os.getenv("LOCAL_STORAGE_PATH", str(ROOT / "data" / "uploads")))
AI_MODE = os.getenv("AI_MODE", "demo")
DEMO_PATH = Path(os.getenv("DEMO_DATA_PATH", str(ROOT / "demo-data")))
MAX_UPLOAD = 15 * 1024 * 1024
