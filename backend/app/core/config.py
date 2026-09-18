"""
Centralized application configuration.

This is a simple, beginner-friendly settings module. It provides one
place to define basic application-level settings so they aren't
scattered or hardcoded across the codebase.

Settings can be overridden using environment variables, but sensible
defaults are provided so the app runs out of the box with no setup.

This project has no database - evidence is simulated JSON data held in
application memory (see app/state.py), so there is no database
configuration here.
"""

import os
from pathlib import Path
from typing import List

# The backend/ directory (two levels up from this file: app/core/config.py).
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings:
    """
    Basic application settings.

    Each setting can be overridden by setting an environment variable
    of the same name before starting the server, e.g.:

        export DEBUG=false
        export APP_NAME="My Custom Name"
        export UPLOAD_DIR="/some/other/path"
    """

    # Human-readable name of the application (shown in API docs, logs, etc.)
    APP_NAME: str = os.getenv("APP_NAME", "Mobile Device Forensic Analysis System")

    # Whether the app is running in development/debug mode.
    # Accepts "true"/"false" (case-insensitive) from the environment.
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # Where uploaded/simulated evidence files (JSON, etc.) are stored.
    # Defaults to backend/uploads.
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))

    # Scratch space for any in-progress file handling (e.g. while a file
    # is being read/validated before it's considered "uploaded"), and
    # where evidence archives are extracted to.
    # Defaults to backend/temp.
    TEMP_DIR: str = os.getenv("TEMP_DIR", str(BASE_DIR / "temp"))

    # Origins allowed to call this API from a browser. The frontend runs
    # on a different origin during development, so CORS has to be handled
    # here on the backend - it cannot be fixed from frontend code.
    #
    # Override with a comma-separated list, e.g.:
    #     export CORS_ORIGINS="http://localhost:5173,http://localhost:3000"
    #
    # The default "*" is fine for a local prototype with no
    # authentication and no credentialed requests. Narrow it before
    # deploying anywhere real.
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]


# A single shared Settings instance, imported wherever configuration
# is needed (e.g. `from app.core.config import settings`).
settings = Settings()
