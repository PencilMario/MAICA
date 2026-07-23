"""Manual local persistence check for the configured LanceDB directory."""

import asyncio
import os

from maica.maica_utils.vector_store import LanceVectorStore


async def main() -> None:
    path = os.getenv("MAICA_VECTOR_DB_PATH", "maica/fs_storage/vector_db")
    dimensions = int(os.getenv("MAICA_EMBEDDING_DIMS", "4096"))
    store = await LanceVectorStore.async_create(path, dimensions=dimensions)
    try:
        print(f"LanceDB ready at {path!r}; table={store.table_name!r}; dimensions={dimensions}")
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
