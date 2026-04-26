"""Runtime configuration for the backend.

This module intentionally reads only phase 0-2 settings. Provider secrets are
left for later integration work.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    demo_mode: str = "mock"
    db_path: str = "./data/nini.db"
    default_terminal_id: str = "demo-kitchen-001"


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        demo_mode=os.getenv("DEMO_MODE", "mock"),
        db_path=os.getenv("DB_PATH", "./data/nini.db"),
        default_terminal_id=os.getenv("DEFAULT_TERMINAL_ID", "demo-kitchen-001"),
    )

