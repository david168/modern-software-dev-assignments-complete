# Exercise 3 (generated): centralized app configuration and paths.
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "app.db"
FRONTEND_DIR = BASE_DIR / "frontend"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    ollama_model: str

    @classmethod
    def from_env(cls) -> Settings:
        db_path = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH)))
        return cls(
            db_path=db_path,
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
        )


settings = Settings.from_env()
