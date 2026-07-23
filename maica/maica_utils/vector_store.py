"""Embedded LanceDB storage for derived MAICA retrieval vectors."""

from __future__ import annotations

import asyncio
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

import lancedb
import pyarrow as pa


_FILTER_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _filter_expr(filters: dict[str, Any] | None) -> str | None:
    if not filters:
        return None
    clauses = []
    for key, value in filters.items():
        if not _FILTER_KEY.fullmatch(key):
            raise ValueError(f"invalid vector filter field: {key}")
        if isinstance(value, bool):
            literal = "true" if value else "false"
        elif isinstance(value, (int, float)):
            literal = str(value)
        elif isinstance(value, str):
            literal = "'" + value.replace("'", "''") + "'"
        else:
            raise ValueError(f"unsupported vector filter value for {key}")
        clauses.append(f"{key} = {literal}")
    return " AND ".join(clauses)


class LanceVectorStore:
    table_name = "maica_rag"

    def __init__(self, db, table, dimensions: int):
        self.db = db
        self.table = table
        self.dimensions = dimensions
        self._write_lock = asyncio.Lock()

    @classmethod
    async def async_create(cls, path: str | Path, dimensions: int, table_name: str | None = None):
        if dimensions <= 0:
            raise ValueError("vector dimensions must be positive")
        name = table_name or cls.table_name

        def open_store():
            db = lancedb.connect(str(Path(path)))
            names = db.list_tables().tables or []
            if name in names:
                table = db.open_table(name)
                vector_type = table.schema.field("vector").type
                actual = vector_type.list_size if pa.types.is_fixed_size_list(vector_type) else None
                if actual != dimensions:
                    raise ValueError(f"vector dimension mismatch: stored={actual}, configured={dimensions}")
            else:
                schema = pa.schema([
                    pa.field("id", pa.string(), nullable=False),
                    pa.field("user_id", pa.int64()),
                    pa.field("chat_session_num", pa.int64()),
                    pa.field("type", pa.string()),
                    pa.field("raw_text", pa.string(), nullable=False),
                    pa.field("is_prod", pa.bool_()),
                    pa.field("vector", pa.list_(pa.float32(), dimensions), nullable=False),
                ])
                table = db.create_table(name, schema=schema)
            return db, table

        db, table = await asyncio.to_thread(open_store)
        return cls(db, table, dimensions)

    @staticmethod
    def _record_id(text: str, filters: dict[str, Any] | None) -> str:
        scope = repr(sorted((filters or {}).items())).encode("utf-8")
        return hashlib.sha256(scope + b"\0" + text.encode("utf-8")).hexdigest()

    async def _embed(self, embedding_conn, data: Iterable[str]):
        texts = list(dict.fromkeys(data))
        if not texts:
            return []
        response = await embedding_conn.make_embedding(input=texts)
        pairs = list(zip(texts, (item.embedding for item in response.data), strict=True))
        for text, vector in pairs:
            if len(vector) != self.dimensions:
                raise ValueError(f"embedding dimension mismatch for {text!r}: {len(vector)} != {self.dimensions}")
        return pairs

    async def sync_texts(self, embedding_conn, data: Iterable[str], unique: str = "raw_text", filters=None):
        if unique != "raw_text":
            raise ValueError("LanceVectorStore only supports raw_text uniqueness")
        requested = set(data)
        expression = _filter_expr(filters)
        async with self._write_lock:
            def read_old():
                query = self.table.search().select(["id", "raw_text"])
                if expression:
                    query = query.where(expression)
                return query.to_arrow().to_pylist()

            old = await asyncio.to_thread(read_old)
            old_by_text = {row["raw_text"]: row["id"] for row in old}
            to_add = requested - old_by_text.keys()
            to_delete = set(old_by_text) - requested
            if to_delete:
                ids = [old_by_text[text] for text in to_delete]
                await asyncio.to_thread(self.table.delete, "id IN (" + ",".join(f"'{item}'" for item in ids) + ")")
            embedded = await self._embed(embedding_conn, to_add)
            if embedded:
                rows = []
                for text, vector in embedded:
                    row = {
                        "id": self._record_id(text, filters),
                        "raw_text": text,
                        "vector": [float(item) for item in vector],
                        "user_id": (filters or {}).get("user_id"),
                        "chat_session_num": (filters or {}).get("chat_session_num", 0),
                        "type": (filters or {}).get("type", "persistent"),
                        "is_prod": (filters or {}).get("is_prod", True),
                    }
                    rows.append(row)
                await asyncio.to_thread(self.table.add, rows)

    async def search(self, embedding_conn, data: Iterable[str], filters=None, topk: int = 5, similarity_min: float = 0.5):
        embedded = await self._embed(embedding_conn, data)
        expression = _filter_expr(filters)
        results: set[str] = set()
        for _, vector in embedded:
            def query():
                search = self.table.search(vector, vector_column_name="vector").distance_type("cosine").limit(topk)
                if expression:
                    search = search.where(expression)
                return search.to_list()

            rows = await asyncio.to_thread(query)
            results.update(row["raw_text"] for row in rows if 1.0 - float(row["_distance"]) >= similarity_min)
        return results

    async def close(self):
        self.table = None
        self.db = None
