from __future__ import annotations

import asyncio

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
