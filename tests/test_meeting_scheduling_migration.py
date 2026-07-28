from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    create_engine,
    inspect,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_meeting_scheduling_migration_round_trip(tmp_path: Path) -> None:
    database_path = tmp_path / "meeting-scheduling-migration.sqlite3"
    async_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["database_url"] = async_url
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    metadata = MetaData()
    Table(
        "meetings",
        metadata,
        Column("id", String(), primary_key=True),
        Column("title", String(), nullable=False),
        Column("created_by", String(), nullable=False),
        Column("start_time", DateTime(), nullable=False),
        Column("end_time", DateTime(), nullable=False),
        Column("status", String(), nullable=False),
        Column("created_at", DateTime(), nullable=False),
    )
    metadata.create_all(engine)
    command.stamp(config, "f2a7c9d418be")

    command.upgrade(config, "9a4d2c7e6b10")
    columns = {column["name"] for column in inspect(engine).get_columns("meetings")}
    assert {"place", "purpose", "personal_gift"}.issubset(columns)

    command.downgrade(config, "f2a7c9d418be")
    columns = {column["name"] for column in inspect(engine).get_columns("meetings")}
    assert "place" not in columns
    assert "purpose" not in columns
    assert "personal_gift" not in columns
    engine.dispose()
