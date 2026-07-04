import asyncio
import json
import sys
import types
from pathlib import Path

import bcrypt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "maica" / "Lib" / "site-packages"))
sys.modules.setdefault("pymilvus", types.SimpleNamespace(AsyncMilvusClient=object))
dateutil_module = types.ModuleType("dateutil")
relativedelta_module = types.ModuleType("dateutil.relativedelta")
parser_module = types.ModuleType("dateutil.parser")
relativedelta_module.relativedelta = object
parser_module.parse = lambda value: value
dateutil_module.parser = parser_module
sys.modules.setdefault("dateutil", dateutil_module)
sys.modules.setdefault("dateutil.relativedelta", relativedelta_module)
sys.modules.setdefault("dateutil.parser", parser_module)

from maica.maica_utils import MaicaSettings
from maica.maica_utils import account_utils
from maica.maica_utils.gvars import G


class FakeAuthPool:
    db_type = "sqlite"

    def __init__(self):
        self.users = []

    async def query_get(self, expression, values=None, fetchall=False):
        expression_lower = expression.lower()
        if "from users where username" in expression_lower:
            return self._find_user("username", values[0])
        if "from users where email" in expression_lower:
            return self._find_user("email", values[0])
        if "select suspended_until from users where id" in expression_lower:
            user = next((u for u in self.users if u["id"] == values[0]), None)
            return (user["suspended_until"],) if user else None
        raise AssertionError(f"Unexpected auth query: {expression}")

    async def query_modify(self, expression, values=None, fetchall=False):
        expression_lower = expression.lower()
        if "insert into users" not in expression_lower:
            raise AssertionError(f"Unexpected auth modification: {expression}")

        if "nickname" in expression_lower:
            username, nickname, email, is_email_confirmed, password = values
        else:
            username, email, password, is_email_confirmed = values
            nickname = None

        user_id = len(self.users) + 1
        self.users.append(
            {
                "id": user_id,
                "username": username,
                "nickname": nickname,
                "email": email,
                "is_email_confirmed": is_email_confirmed,
                "password": password,
                "suspended_until": None,
            }
        )
        return 1, user_id

    def _find_user(self, key, value):
        user = next((u for u in self.users if u[key] == value), None)
        if not user:
            return None
        return (
            user["id"],
            user["username"],
            user["nickname"],
            user["email"],
            user["is_email_confirmed"],
            user["password"],
        )


class FakeMaicaPool:
    db_type = "sqlite"

    async def query_get(self, expression, values=None, fetchall=False):
        if "from account_status" in expression.lower():
            return None
        raise AssertionError(f"Unexpected maica query: {expression}")

    async def query_modify(self, expression, values=None, fetchall=False):
        if "account_status" in expression.lower():
            return 1, 1
        raise AssertionError(f"Unexpected maica modification: {expression}")


def encrypted_token(payload):
    account_utils.pkg_init_account_utils()
    return account_utils.encrypt_token(json.dumps(payload, ensure_ascii=False))


def run(coro):
    return asyncio.run(coro)


async def verify_with_serviceonly(payload, auth_pool):
    previous = G.A.SERVICE_ONLY
    G.A.SERVICE_ONLY = "1"
    try:
        cursor = account_utils.AccountCursor(MaicaSettings(), auth_pool, FakeMaicaPool())
        return await cursor.hashing_verify(encrypted_token(payload)), cursor
    finally:
        G.A.SERVICE_ONLY = previous


def test_serviceonly_creates_missing_username_account():
    auth_pool = FakeAuthPool()

    result, cursor = run(
        verify_with_serviceonly(
            {"username": "service_user", "password": "ignored"},
            auth_pool,
        )
    )

    assert result == (True, None)
    assert len(auth_pool.users) == 1
    assert auth_pool.users[0]["username"] == "service_user"
    assert auth_pool.users[0]["email"] == "service_user@serviceonly.local"
    assert auth_pool.users[0]["is_email_confirmed"] == 1
    assert cursor.settings.verification.user_id == 1
    assert cursor.settings.verification.username == "service_user"


def test_serviceonly_skips_password_check_for_existing_account():
    auth_pool = FakeAuthPool()
    auth_pool.users.append(
        {
            "id": 1,
            "username": "existing",
            "nickname": "Existing",
            "email": "existing@example.com",
            "is_email_confirmed": 1,
            "password": bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode("utf-8"),
            "suspended_until": None,
        }
    )

    result, cursor = run(
        verify_with_serviceonly(
            {"username": "existing", "password": "wrong-password"},
            auth_pool,
        )
    )

    assert result == (True, None)
    assert len(auth_pool.users) == 1
    assert cursor.settings.verification.user_id == 1
    assert cursor.settings.verification.username == "existing"


async def verify_with_normal_auth(payload, auth_pool):
    previous = G.A.SERVICE_ONLY
    G.A.SERVICE_ONLY = "0"
    try:
        cursor = account_utils.AccountCursor(MaicaSettings(), auth_pool, FakeMaicaPool())
        return await cursor.hashing_verify(encrypted_token(payload)), cursor
    finally:
        G.A.SERVICE_ONLY = previous


def test_normal_auth_sets_verified_identity_after_password_check():
    auth_pool = FakeAuthPool()
    auth_pool.users.append(
        {
            "id": 1,
            "username": "normal",
            "nickname": "Normal",
            "email": "normal@example.com",
            "is_email_confirmed": 1,
            "password": bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode("utf-8"),
            "suspended_until": None,
        }
    )

    result, cursor = run(
        verify_with_normal_auth(
            {"username": "normal", "password": "correct-password"},
            auth_pool,
        )
    )

    assert result == (True, None)
    assert cursor.settings.verification.user_id == 1
    assert cursor.settings.verification.username == "normal"
