import asyncio
from types import SimpleNamespace

from maica.maica_utils.session_late import SessionPersistentLlmMixin


class FakeVectorStore:
    def __init__(self):
        self.sync_calls = []
        self.search_calls = []

    async def sync_texts(self, embedding_conn, data, unique="raw_text", filters=None):
        self.sync_calls.append((embedding_conn, list(data), unique, filters))

    async def search(self, embedding_conn, data, filters=None, topk=5, similarity_min=0.5):
        self.search_calls.append((embedding_conn, list(data), filters, topk, similarity_min))
        return {"remembered"}


def _session(vector_store):
    fsc = SimpleNamespace(
        vector_pool=vector_store,
        embedding_conn="embedding",
        is_vector_ready=True,
        maica_settings=SimpleNamespace(
            verification=SimpleNamespace(user_id=42),
        ),
    )
    session = object.__new__(SessionPersistentLlmMixin)
    session.fsc = fsc
    session.session_num = 3
    session.form_info = lambda: ["a", "b"]
    return session


def test_session_writes_to_vector_store_with_user_scope() -> None:
    async def scenario():
        store = FakeVectorStore()
        await _session(store).to_vector_store(["memory"])

        assert store.sync_calls == [
            ("embedding", ["memory"], "raw_text", {
                "user_id": 42,
                "chat_session_num": 3,
            }),
        ]

    asyncio.run(scenario())


def test_session_searches_vector_store_with_user_scope() -> None:
    async def scenario():
        store = FakeVectorStore()
        result = await _session(store).filter_vector_store("query", topk=7)

        assert result == {"remembered"}
        assert store.search_calls == [
            ("embedding", ["query"], {
                "user_id": 42,
                "chat_session_num": 3,
            }, 7, 0.5),
        ]

    asyncio.run(scenario())
