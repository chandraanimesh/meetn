import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger("app.infrastructure.database.readiness")


class SQLAlchemyReadinessProbe:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> bool:
        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception(
                "database_readiness_failed",
                extra={"operation": "select_1"},
            )
            return False
        return True
