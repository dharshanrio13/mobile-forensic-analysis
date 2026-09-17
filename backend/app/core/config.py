"""
Centralized application configuration.

This is a simple, beginner-friendly settings module. It provides one
place to define basic application-level settings so they aren't
scattered or hardcoded across the codebase.

Settings can be overridden using environment variables, but sensible
defaults are provided so the app runs out of the box with no setup.
"""

import os
from pathlib import Path

# The backend/ directory (two levels up from this file: app/core/config.py).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Default location for the SQLite database file: backend/app/database/app.db
DEFAULT_DATABASE_URL = f"sqlite:///{BASE_DIR / 'app' / 'database' / 'app.db'}"


class Settings:
    """
    Basic application settings.

    Each setting can be overridden by setting an environment variable
    of the same name before starting the server, e.g.:

        export DEBUG=false
        export APP_NAME="My Custom Name"
        export DATABASE_URL="sqlite:///./somewhere_else.db"
    """

    # Human-readable name of the application (shown in API docs, logs, etc.)
    APP_NAME: str = os.getenv("APP_NAME", "Mobile Device Forensic Analysis System")

    # Whether the app is running in development/debug mode.
    # Accepts "true"/"false" (case-insensitive) from the environment.
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # SQLAlchemy database URL. Defaults to a local SQLite file stored
    # inside app/database/, kept out of version control (see .gitignore).
    DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


# A single shared Settings instance, imported wherever configuration
# is needed (e.g. `from app.core.config import settings`).
settings = Settings()

