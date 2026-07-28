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
MULTIMODAL_COLUMNS = {
    "conversation_id",
    "input_modality",
    "media_hash",
    "media_type",
    "media_size",
    "provider",
    "model_name",
    "prompt_version",
    "selected_action_id",
    "entitlement_decision",
    "tts_allowed",
    "latency_ms",
    "status",
    "error_code",
}


def test_multimodal_audit_migration_round_trip(tmp_path: Path) -> None:
    database_path = tmp_path / "multimodal-audit-migration.sqlite3"
    async_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["database_url"] = async_url
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_audit_events_conversation_created")
        connection.exec_driver_sql("DROP INDEX ix_audit_events_media_hash")
        for column_name in MULTIMODAL_COLUMNS:
            connection.exec_driver_sql(
                f'ALTER TABLE audit_events DROP COLUMN "{column_name}"'
            )
    command.stamp(config, "9a4d2c7e6b10")
    columns = {column["name"] for column in inspect(engine).get_columns("audit_events")}
    assert MULTIMODAL_COLUMNS.isdisjoint(columns)

    command.upgrade(config, "d4e9a1c7b205")
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("audit_events")}
    indexes = {index["name"] for index in inspector.get_indexes("audit_events")}
    assert MULTIMODAL_COLUMNS.issubset(columns)
    assert {
        "ix_audit_events_media_hash",
        "ix_audit_events_conversation_created",
    }.issubset(indexes)

    command.downgrade(config, "9a4d2c7e6b10")
    columns = {column["name"] for column in inspect(engine).get_columns("audit_events")}
    assert MULTIMODAL_COLUMNS.isdisjoint(columns)
    engine.dispose()
