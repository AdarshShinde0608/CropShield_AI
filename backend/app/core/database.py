from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import Settings


async def create_indexes(database: AsyncIOMotorDatabase) -> None:
    await database.users.create_index("email", unique=True)

    await database.fields.create_index([("geometry", "2dsphere")])
    await database.fields.create_index("region_id")
    await database.fields.create_index("field_id", unique=True)

    await database.seasons.create_index("season_id", unique=True)

    await database.observations.create_index(
        [("field_id", 1), ("season_id", 1), ("date", 1)],
        unique=True,
    )
    await database.rainfall.create_index(
        [("region_id", 1), ("season_id", 1), ("date", 1)]
    )
    await database.field_results.create_index(
        [("region_id", 1), ("season_id", 1), ("run_id", 1), ("priority_rank", 1)]
    )
    await database.analysis_runs.create_index("run_id", unique=True)
    await database.analysis_runs.create_index([("created_at", -1)])
    await database.validation_reports.create_index("run_id")
    await database.actions.create_index([("field_id", 1), ("user_id", 1)])
    await database.actions.create_index("action_id", unique=True)


async def connect_to_mongo(
    settings: Settings,
) -> tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=5000,
    )
    try:
        await client.admin.command("ping")
        database = client[settings.mongodb_db]
        await create_indexes(database)
    except Exception:
        client.close()
        raise
    return client, database


def get_db(request: Request) -> AsyncIOMotorDatabase:
    database = getattr(request.app.state, "db", None)
    if database is None:
        raise RuntimeError("MongoDB is not initialized")
    return database