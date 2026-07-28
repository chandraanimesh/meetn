from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.infrastructure.database.base import Base
from app.infrastructure.database.models import audit_event as _audit_models  # noqa: F401
from app.infrastructure.database.models import meeting as _meeting_models  # noqa: F401
from app.infrastructure.database.models import recording as _recording_models  # noqa: F401
from app.infrastructure.database.models import user as _user_models  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_recording_and_membership_migration_round_trip(tmp_path: Path) -> None:
    database_path = tmp_path / "recording-migration.sqlite3"
    async_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["database_url"] = async_url
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    pre_revision_tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in {"recordings", "memberships"}
    ]
    Base.metadata.create_all(engine, tables=pre_revision_tables)
    command.stamp(config, "c6b2a8d4e901")

    command.upgrade(config, "f2a7c9d418be")
    inspector = inspect(engine)

    assert {"recordings", "memberships"}.issubset(inspector.get_table_names())
    assert {column["name"] for column in inspector.get_columns("recordings")} == {
        "id",
        "meeting_id",
        "processing_status",
        "required_plan",
        "created_at",
    }
    assert {column["name"] for column in inspector.get_columns("memberships")} == {
        "id",
        "user_id",
        "plan",
        "status",
        "valid_until",
        "updated_at",
    }

    command.downgrade(config, "c6b2a8d4e901")
    inspector = inspect(engine)
    assert "recordings" not in inspector.get_table_names()
    assert "memberships" not in inspector.get_table_names()
    engine.dispose()
