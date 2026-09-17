"""
Very small test: does the database get created and can it be opened?

Run from anywhere (project root recommended):

    python tests/test_database.py

or, if you have pytest installed:

    pytest tests/

This loads database/connection.py and database/init_db.py directly by file
path (importlib), instead of `import database`. That avoids a real-world
gotcha: if anything else on your machine is also importable as `database`
(e.g. a globally pip-installed package with that name), a plain
`import database` can silently grab the wrong one. Loading by path always
gets *this* project's files, no matter what.
"""

import importlib.util
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"


def _load_module(name: str, file_path: Path):
    """Load a single .py file as a module, bypassing sys.path lookup."""
    if not file_path.exists():
        raise FileNotFoundError(
            f"Expected file not found: {file_path}\n"
            f"Check that your folder structure matches:\n"
            f"  {PROJECT_ROOT.name}/database/{file_path.name}"
        )
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# connection.py has no local imports, so load it first.
connection_module = _load_module("connection", DATABASE_DIR / "connection.py")

# init_db.py does `from .connection import ...`, which needs a real package
# context. Register a lightweight "database" package pointing at our folder
# so that relative import resolves, then load init_db.py through it.
database_pkg = types.ModuleType("database")
database_pkg.__path__ = [str(DATABASE_DIR)]
sys.modules["database"] = database_pkg
sys.modules["database.connection"] = connection_module

init_db_module = _load_module("database.init_db", DATABASE_DIR / "init_db.py")

DATABASE_PATH = connection_module.DATABASE_PATH
get_connection = connection_module.get_connection
init_db = init_db_module.init_db


def test_database_can_be_opened():
    init_db()

    # 1. The file exists on disk.
    assert DATABASE_PATH.exists(), f"Database file missing: {DATABASE_PATH}"

    # 2. SQLite answers a query through it.
    connection = get_connection()
    try:
        result = connection.execute("SELECT 1 AS ok;").fetchone()
        assert result["ok"] == 1
    finally:
        connection.close()


if __name__ == "__main__":
    test_database_can_be_opened()
    print("PASS - database created and opened successfully.")
    print(f"Database file: {DATABASE_PATH}")
