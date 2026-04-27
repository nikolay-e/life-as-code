# pyright: reportGeneralTypeIssues=false
import os
import subprocess
import sys
import uuid

import psycopg2
import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5434"))
PG_USER = os.environ.get("POSTGRES_USER", "life_as_code_user")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "testpass")  # noqa: S105 pragma: allowlist secret


@pytest.fixture
def fresh_db():
    db_name = f"life_as_code_bootstrap_{uuid.uuid4().hex[:8]}"
    admin = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASS,
        dbname="postgres",
    )
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute(f'CREATE DATABASE "{db_name}"')
    admin.close()
    yield db_name
    admin = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASS,
        dbname="postgres",
    )
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{db_name}'"
    )
    cur.execute(f'DROP DATABASE "{db_name}"')
    admin.close()


def _db_url(db_name: str) -> str:
    return (
        f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@"
        f"{PG_HOST}:{PG_PORT}/{db_name}"
    )


def test_init_db_stamps_alembic_head(fresh_db):
    url = _db_url(fresh_db)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'src'); "
            "from database import init_db; init_db()",
        ],
        check=True,
        cwd=project_root,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
    )

    engine = create_engine(url)
    with engine.connect() as conn:
        version = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
        assert version is not None
        assert version != ""

        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'bot_messages'"
            )
        ).fetchone()
        assert rows is not None, "bot_messages table not created"
    engine.dispose()


def test_alembic_upgrade_head_after_bootstrap_is_noop(fresh_db):
    url = _db_url(fresh_db)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "DATABASE_URL": url}

    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'src'); "
            "from database import init_db; init_db()",
        ],
        check=True,
        cwd=project_root,
        env=env,
        capture_output=True,
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head failed after init_db bootstrap: "
        f"stdout={result.stdout} stderr={result.stderr}"
    )
