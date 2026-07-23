import asyncio
from contextlib import asynccontextmanager

import bcrypt
import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from maica.maica_utils import (
    DatabaseUtils,
    FullSocketsContainer,
    G,
    MaicaInputWarning,
    SqlBaseAuth,
    SqlUser,
)
from maica.maica_utils.database_utils import ReadOnlySession


@asynccontextmanager
async def service_only_database(url="sqlite+aiosqlite:///:memory:"):
    engine = create_async_engine(url)
    old_engine = DatabaseUtils.engine_auth
    old_factory = DatabaseUtils.SessionAuth
    old_service_only = G.A.SERVICE_ONLY
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SqlBaseAuth.metadata.create_all)
        DatabaseUtils.engine_auth = engine
        DatabaseUtils.SessionAuth = async_sessionmaker(
            engine,
            class_=ReadOnlySession,
            expire_on_commit=False,
        )
        G.A.SERVICE_ONLY = "1"
        yield engine
    finally:
        G.A.SERVICE_ONLY = old_service_only
        DatabaseUtils.SessionAuth = old_factory
        DatabaseUtils.engine_auth = old_engine
        await engine.dispose()


async def load_users(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        return (await session.scalars(sqlalchemy.select(SqlUser))).all()


def test_service_only_accepts_malformed_and_absent_tokens_as_one_identity():
    async def scenario():
        async with service_only_database() as engine:
            malformed_login = FullSocketsContainer()
            absent_login = FullSocketsContainer()

            assert await malformed_login.login("not-an-rsa-token") is True
            assert await absent_login.login() is True

            malformed_identity = malformed_login.maica_settings.verification
            absent_identity = absent_login.maica_settings.verification
            assert malformed_identity.username == "service_only"
            assert absent_identity.username == "service_only"
            assert malformed_identity.user_id == absent_identity.user_id
            assert len(await load_users(engine)) == 1

    asyncio.run(scenario())


def test_service_only_creates_fixed_confirmed_account_once():
    async def scenario():
        async with service_only_database() as engine:
            first_login = FullSocketsContainer()
            second_login = FullSocketsContainer()

            await first_login.login("first-token")
            await second_login.login("second-token")

            users = await load_users(engine)
            assert len(users) == 1
            user = users[0]
            assert user.username == "service_only"
            assert user.nickname == "Service Only"
            assert user.email == "service_only@localhost.local"
            assert user.is_email_confirmed is True
            assert bcrypt.checkpw(b"first-token", user.password.encode()) is False
            assert bcrypt.checkpw(b"second-token", user.password.encode()) is False

    asyncio.run(scenario())


def test_service_only_concurrent_first_login_converges_on_one_account(tmp_path):
    async def scenario():
        database = tmp_path / "service-only.sqlite3"
        async with service_only_database(f"sqlite+aiosqlite:///{database.as_posix()}") as engine:
            callers = [FullSocketsContainer(), FullSocketsContainer()]
            await asyncio.gather(*(caller.login("ignored") for caller in callers))

            users = await load_users(engine)
            assert len(users) == 1
            assert callers[0].maica_settings.verification.user_id == users[0].id
            assert callers[1].maica_settings.verification.user_id == users[0].id

    asyncio.run(scenario())


def test_normal_mode_still_rejects_malformed_token():
    async def scenario():
        async with service_only_database():
            G.A.SERVICE_ONLY = "0"
            with pytest.raises(MaicaInputWarning):
                await FullSocketsContainer().login("not-an-rsa-token")

    asyncio.run(scenario())
