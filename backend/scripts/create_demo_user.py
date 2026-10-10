import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.database import connect_to_mongo, create_indexes
from app.core.security import hash_password
from app.schemas.auth import RegisterRequest


async def main() -> None:
    email = os.environ.get("DEMO_EMAIL")
    password = os.environ.get("DEMO_PASSWORD")
    if not email or not password:
        raise RuntimeError("DEMO_EMAIL and DEMO_PASSWORD must both be set")

    user_request = RegisterRequest(
        email=email,
        password=password,
        name="Demo Officer",
        language="en",
    )
    client, database = await connect_to_mongo(get_settings())
    try:
        await create_indexes(database)
        await database.users.insert_one(
            {
                "email": str(user_request.email),
                "password_hash": hash_password(user_request.password.get_secret_value()),
                "name": user_request.name,
                "role": "officer",
                "language": user_request.language,
            }
        )
    except DuplicateKeyError as exc:
        raise RuntimeError("A user with DEMO_EMAIL already exists") from exc
    finally:
        client.close()
    print(f"Created demo user: {user_request.email}")


if __name__ == "__main__":
    asyncio.run(main())
