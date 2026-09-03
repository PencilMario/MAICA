from __future__ import annotations

import asyncio

import lancedb
import pyarrow as pa
import pytest

from maica.maica_utils.vector_store import LanceVectorStore


class FakeEmbedding:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def make_embedding(self, *, input: list[str]):
        self.calls.append(list(input))
        vectors = {
            "alpha": [1.0, 0.0, 0.0, 0.0],
            "beta": [0.0, 1.0, 0.0, 0.0],
            "gamma": [0.7, 0.7, 0.0, 0.0],
        }

        class Item:
            def __init__(self, embedding):
                self.embedding = embedding

        class Response:
            def __init__(self, data):
                self.data = data

        return Response([Item(vectors[text]) for text in input])


def run(coro):
    return asyncio.run(coro)


def test_sync_texts_persists_and_diffs_without_reembedding(tmp_path) -> None:
    async def scenario() -> None:
        embeddings = FakeEmbedding()
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        await store.sync_texts(embeddings, ["alpha", "beta"], filters={"user_id": -1})
        await store.sync_texts(embeddings, ["alpha", "gamma"], filters={"user_id": -1})
        assert sorted(embeddings.calls[0]) == ["alpha", "beta"]
        assert embeddings.calls[1] == ["gamma"]
        assert await store.search(embeddings, ["alpha"], filters={"user_id": -1}, similarity_min=0) == {"alpha", "gamma"}
        await store.close()

        reopened = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        assert await reopened.search(embeddings, ["alpha"], filters={"user_id": -1}, similarity_min=0) == {"alpha", "gamma"}
        await reopened.close()

    run(scenario())


def test_search_applies_scope_and_similarity_threshold(tmp_path) -> None:
    async def scenario() -> None:
        embeddings = FakeEmbedding()
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        await store.sync_texts(embeddings, ["alpha"], filters={"user_id": -1})
        await store.sync_texts(embeddings, ["alpha"], filters={"user_id": 7})
        assert await store.search(embeddings, ["alpha"], filters={"user_id": 7}, similarity_min=0.99) == {"alpha"}
        assert await store.search(embeddings, ["beta"], filters={"user_id": -1}, similarity_min=0.99) == set()
        await store.close()

    run(scenario())


def test_search_uses_cosine_similarity(tmp_path) -> None:
    async def scenario() -> None:
        embeddings = FakeEmbedding()
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        await store.sync_texts(embeddings, ["gamma"], filters={"user_id": -1})
        assert await store.search(embeddings, ["alpha"], filters={"user_id": -1}, similarity_min=0.7) == {"gamma"}
        await store.close()

    run(scenario())


def test_dimension_mismatch_is_rejected(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        await store.close()
        with pytest.raises(ValueError, match="dimension"):
            await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=8)

    run(scenario())


def test_sync_texts_rejects_non_string_rows(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(TypeError, match="raw_text"):
            await store.sync_texts(FakeEmbedding(), ["ok", 7])
        await store.close()

    run(scenario())


def test_sync_texts_rejects_unhashable_rows_as_raw_text(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(TypeError, match="raw_text"):
            await store.sync_texts(FakeEmbedding(), ["alpha", ["not", "text"]])
        await store.close()

    run(scenario())


def test_filters_reject_unknown_fields_before_query(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(ValueError, match="filter field"):
            await store.sync_texts(FakeEmbedding(), ["alpha"], filters={"unknown": 1})
        await store.close()

    run(scenario())


def test_search_rejects_invalid_limits(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(ValueError, match="topk"):
            await store.search(FakeEmbedding(), ["alpha"], topk=0)
        with pytest.raises(ValueError, match="similarity"):
            await store.search(FakeEmbedding(), ["alpha"], similarity_min=float("nan"))
        await store.close()

    run(scenario())


def test_scope_defaults_do_not_create_duplicate_rows(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        embeddings = FakeEmbedding()
        await store.sync_texts(embeddings, ["alpha"], filters={"user_id": -1})
        await store.sync_texts(
            embeddings,
            ["alpha"],
            filters={"user_id": -1, "chat_session_num": 0, "type": "persistent", "is_prod": True},
        )
        rows = await asyncio.to_thread(store.table.to_arrow)
        assert rows.num_rows == 1
        await store.close()

    run(scenario())


def test_existing_non_float32_vector_schema_is_rejected(tmp_path) -> None:
    async def scenario() -> None:
        db = await asyncio.to_thread(lancedb.connect, str(tmp_path / "vectors"))
        await asyncio.to_thread(
            db.create_table,
            "maica_rag",
            schema=pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float64(), 4)),
            ]),
        )
        with pytest.raises(ValueError, match="vector schema"):
            await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)

    run(scenario())


def test_existing_incomplete_schema_is_rejected(tmp_path) -> None:
    async def scenario() -> None:
        db = await asyncio.to_thread(lancedb.connect, str(tmp_path / "vectors"))
        await asyncio.to_thread(
            db.create_table,
            "maica_rag",
            schema=pa.schema([
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), 4)),
            ]),
        )
        with pytest.raises(ValueError, match="missing fields"):
            await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)

    run(scenario())


def test_filter_values_must_match_supported_scalar_types(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(ValueError, match="user_id"):
            await store.sync_texts(FakeEmbedding(), ["alpha"], filters={"user_id": "7"})
        with pytest.raises(ValueError, match="is_prod"):
            await store.search(FakeEmbedding(), ["alpha"], filters={"is_prod": 1})
        await store.close()

    run(scenario())


def test_search_validates_filters_before_embedding(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(ValueError, match="filter field"):
            await store.search(FakeEmbedding(), ["not-in-fixture"], filters={"unknown": 1})
        await store.close()

    run(scenario())


def test_search_validates_texts_before_embedding(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(TypeError, match="vector text data"):
            await store.search(FakeEmbedding(), "alpha")
        await store.close()

    run(scenario())


def test_filters_must_be_a_mapping(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(TypeError, match="filters"):
            await store.sync_texts(FakeEmbedding(), ["alpha"], filters=[("user_id", -1)])
        with pytest.raises(TypeError, match="filters"):
            await store.search(FakeEmbedding(), ["alpha"], filters="user_id = -1")
        with pytest.raises(TypeError, match="filters"):
            await store.search(FakeEmbedding(), ["alpha"], filters=[])
        await store.close()

    run(scenario())


def test_dimensions_must_be_a_positive_integer(tmp_path) -> None:
    async def scenario() -> None:
        for dimensions in (True, 4.0, 0, -1):
            with pytest.raises(ValueError, match="dimensions"):
                await LanceVectorStore.async_create(tmp_path / str(dimensions), dimensions=dimensions)

    run(scenario())


def test_filter_field_names_must_be_strings(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        with pytest.raises(ValueError, match="filter field"):
            await store.search(FakeEmbedding(), ["alpha"], filters={1: -1})
        await store.close()

    run(scenario())


def test_closed_store_rejects_reads_and_writes(tmp_path) -> None:
    async def scenario() -> None:
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        await store.close()
        with pytest.raises(RuntimeError, match="closed"):
            await store.sync_texts(FakeEmbedding(), ["alpha"])
        with pytest.raises(RuntimeError, match="closed"):
            await store.search(FakeEmbedding(), ["alpha"])
        await store.close()

    run(scenario())


def test_close_releases_underlying_lancedb_connection() -> None:
    class Connection:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class Database:
        def __init__(self) -> None:
            self._conn = Connection()

    async def scenario() -> None:
        database = Database()
        store = LanceVectorStore(database, object(), dimensions=4)
        await store.close()
        assert database._conn.closed

    run(scenario())


def test_sync_texts_serializes_concurrent_writes(tmp_path) -> None:
    async def scenario() -> None:
        class SlowEmbedding(FakeEmbedding):
            active = 0
            max_active = 0

            async def make_embedding(self, *, input: list[str]):
                type(self).active += 1
                type(self).max_active = max(type(self).max_active, type(self).active)
                try:
                    await asyncio.sleep(0.02)
                    return await super().make_embedding(input=input)
                finally:
                    type(self).active -= 1

        embeddings = SlowEmbedding()
        store = await LanceVectorStore.async_create(tmp_path / "vectors", dimensions=4)
        await asyncio.gather(
            store.sync_texts(embeddings, ["alpha"], filters={"user_id": 1}),
            store.sync_texts(embeddings, ["beta"], filters={"user_id": 2}),
        )
        assert embeddings.max_active == 1
        rows = await asyncio.to_thread(store.table.to_arrow)
        assert rows.num_rows == 2
        await store.close()

    run(scenario())
