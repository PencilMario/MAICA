# LanceDB Embedded Vector Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use aegis:subagent-driven-development (recommended) or aegis:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Milvus with an embedded LanceDB store that supports MAICA RAG and `maica-gnrc` in a Windows Nuitka one-file build.

**Architecture:** A backend-neutral async manager owns one LanceDB table and moves synchronous LanceDB work to worker threads. Existing OpenAI-compatible embeddings remain unchanged; derived vectors are rebuilt from source data and no Milvus compatibility remains.

**Tech Stack:** Python 3.12+, LanceDB, PyArrow, asyncio, pytest, Nuitka.

**Baseline / Authority Refs:** `docs/aegis/specs/2026-07-23-lancedb-vector-store-design.md`, `document/MAINTENANCE.md`, existing connection lifecycle in `maica/maica_starter.py`.

**Compatibility Boundary:** Core chat, relational persistence, embedding and reranker APIs remain stable. Similarity thresholds keep the existing larger-is-better meaning. Existing Milvus data and configuration are retired.

**Verification:** Focused pytest tests, full `pytest -q`, Ruff, a native Python LanceDB persistence probe, and a Windows Nuitka one-file persistence/search probe.

---

## File ownership map

- `maica/maica_utils/vector_store.py`: LanceDB schema, filtering, diff synchronization, search, locking, lifecycle.
- `maica/maica_utils/connection_utils.py`: construct the vector store and retain AI connections.
- `maica/maica_utils/session_late.py`, `maica/mtools/generic/rag.py`: backend-neutral consumers.
- `maica/maica_utils/fsc_late.py`, `maica/maica_utils/maica_utils.py`, service entry points: readiness and typing.
- `maica/initializer/migrations/migration_4.py`: relational migration only after Milvus retirement.
- `requirements.txt`, `maica/env_basis`, `build_local.ps1`: dependency, configuration, packaging.
- `tests/test_vector_store.py`: deterministic isolated vector-store behavior.
- `examples/lancedb_smoke.py`, `examples/lancedb_nuitka_probe.py`: manual and packaged persistence probes.

### Task 1: Prove LanceDB works in the target runtime and Nuitka build

**Files:**
- Create: `examples/lancedb_nuitka_probe.py`
- Modify: `build_local.ps1`

**Why this task exists:** Native LanceDB/PyArrow loading is the largest unknown and is a hard gate before migrating business code.

**Impact / Compatibility:** No runtime MAICA behavior changes. The probe writes only beneath a supplied temporary directory.

**Verification:** `python examples/lancedb_nuitka_probe.py <temp-path>` and the same command compiled with Nuitka must print `LANCEDB_PROBE_OK` twice across create/reopen.

- [ ] Add a probe that connects with `lancedb.connect(path)`, creates a table containing `id`, `user_id`, `raw_text`, and a four-dimensional vector, queries by cosine distance with `user_id = -1`, closes, reconnects, and asserts the same result.
- [ ] Install the declared LanceDB/PyArrow dependencies and run the Python probe; verify `LANCEDB_PROBE_OK`.
- [ ] Compile the probe with `python -m nuitka --onefile --include-package=lancedb --include-package=pyarrow --output-dir=<temp-build> examples/lancedb_nuitka_probe.py`.
- [ ] Run the executable twice against an external temporary data path and verify `LANCEDB_PROBE_OK` both times.
- [ ] Record any required Nuitka data/DLL collection flags in `build_local.ps1`.
- [ ] Commit the feasibility slice with `build(vector): 验证 LanceDB 的 Nuitka 打包能力`.

### Task 2: Implement the backend-neutral LanceDB manager with TDD

**Files:**
- Create: `maica/maica_utils/vector_store.py`
- Create: `tests/test_vector_store.py`
- Modify: `maica/maica_utils/__init__.py`

**Why this task exists:** Centralize schema and search semantics so business layers do not depend on LanceDB APIs.

**Impact / Compatibility:** The manager accepts existing embedding managers through their `make_embedding(input=...)` contract and returns `set[str]` as current callers expect.

**Verification:** `python -m pytest tests/test_vector_store.py -q`.

- [ ] Write failing tests using a temporary directory and a fake embedding manager for table creation, close/reopen persistence, scoped diff add/delete, no re-embedding of unchanged strings, `user_id` isolation, Top-K ordering, threshold conversion, dimension mismatch, and concurrent writes.
- [ ] Run the focused tests and confirm failure because `LanceVectorStore` does not exist.
- [ ] Implement `LanceVectorStore.async_create(path, table_name, dimensions)`, `sync_texts(embedding_conn, data, unique="raw_text", filters=None)`, `search(embedding_conn, data, filters=None, topk=5, similarity_min=0.5)`, and `close()`.
- [ ] Store vectors as fixed-size float32 lists, generate stable string IDs from scope and text, escape/validate supported scalar filters, use `asyncio.to_thread()` for database work, and serialize writes with `asyncio.Lock`.
- [ ] Convert `_distance` with `1.0 - distance`, preserve larger-is-better thresholds, and raise a clear MAICA database warning when stored and configured dimensions differ.
- [ ] Run focused tests until they pass, then run `python -m ruff check maica/maica_utils/vector_store.py tests/test_vector_store.py`.
- [ ] Commit with `feat(vector): 增加 LanceDB 嵌入式向量存储`.

### Task 3: Replace Milvus consumers and retire its owners

**Files:**
- Modify: `maica/maica_utils/connection_utils.py`
- Modify: `maica/maica_utils/connection_mixin.py`
- Modify: `maica/maica_utils/session_late.py`
- Modify: `maica/mtools/generic/rag.py`
- Modify: `maica/mfocus/agent_modules.py`
- Modify: `maica/maica_http.py`
- Modify: `maica/maica_utils/fsc_late.py`
- Modify: `maica/maica_utils/maica_utils.py`
- Modify: `maica/maica_utils/__init__.py`
- Modify: `maica/initializer/migrations/migration_4.py`
- Modify: relevant existing tests.

**Repair Track:** Milvus-specific APIs currently leak from connection code into sessions and HTTP handlers. Make `LanceVectorStore` the canonical owner and preserve the embedding/search behavior through neutral names.

**Retirement Track:** Delete `MilvusDbConnectionManager`, `MilvusSearchMixin`, pymilvus imports, collection initialization, and active names `to_milvus`/`filter_milvus`. No fallback remains.

**Verification:** `rg -n "pymilvus|Milvus|MILVUS|to_milvus|filter_milvus" maica tests` returns no active implementation matches, and relevant tests pass.

- [ ] Add failing integration tests showing `ConnUtils.vector_pool()` constructs the configured LanceDB manager and RAG readiness no longer depends on `MILVUS_ADDR`.
- [ ] Rename session operations to `to_vector_store()` and `filter_vector_store()` and update all consumers.
- [ ] Move embedding-assisted calls to `LanceVectorStore.sync_texts()` and `.search()`.
- [ ] Remove Milvus schema work from migration 4 while keeping its relational migration unchanged.
- [ ] Update socket container types and public exports to use `LanceVectorStore`.
- [ ] Run focused database, session, HTTP, and shutdown tests.
- [ ] Commit with `refactor(rag): 使用 LanceDB 替换 Milvus 调用链`.

### Task 4: Replace deployment configuration, dependencies, docs, and examples

**Files:**
- Modify: `requirements.txt`
- Modify: `maica/env_basis`
- Modify: `README.md`
- Modify: `README_EN.md`
- Modify: `document/Backend Deployment.md`
- Modify: `document/MAINTENANCE.md`
- Delete: `examples/milvus_smoke.py`
- Create: `examples/lancedb_smoke.py`

**Repair Track:** Windows installs currently silently omit Milvus Lite despite the declared extra. Declare LanceDB directly and document its external writable path.

**Retirement Track:** Remove all `MAICA_MILVUS_*` options and Milvus smoke instructions. The only vector database option becomes `MAICA_VECTOR_DB_PATH`, defaulting to `fs_storage/vector_db`.

**Verification:** Search the non-deprecated project for Milvus references, generate a configuration template, and import MAICA with the new dependency set.

- [ ] Add `lancedb` and compatible `pyarrow` requirements and remove `pymilvus[milvus_lite]`.
- [ ] Replace four Milvus environment options with `MAICA_VECTOR_DB_PATH` and document the persistent external directory requirement.
- [ ] Replace the server connectivity smoke script with a local create/reopen/search smoke script.
- [ ] Update deployment, maintenance, and quick-start text.
- [ ] Run documentation/config searches and `python -m pytest -q`.
- [ ] Commit with `docs(rag): 更新 LanceDB 本地部署说明`.

### Task 5: Complete verification and evidence

**Files:**
- Modify: `docs/aegis/INDEX.md`
- Create: `docs/aegis/work/2026-07-23-lancedb-vector-store/50-evidence.md`

**Why this task exists:** The replacement is complete only when source behavior and packaged native-library behavior are both demonstrated.

**Verification:** All commands below exit zero and evidence records exact outputs.

- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m ruff check maica tests examples`.
- [ ] Run `python -m compileall -q maica tests examples`.
- [ ] Run the native LanceDB persistence smoke test.
- [ ] Rebuild and rerun the Nuitka one-file probe against an external directory.
- [ ] Run `rg -n "pymilvus|MAICA_MILVUS|Milvus" maica tests examples requirements.txt README.md README_EN.md document/Backend\ Deployment.md document/MAINTENANCE.md` and verify no active references remain.
- [ ] Record commands, versions, results, and any residual package-size risk in the evidence file.
- [ ] Commit with `test(rag): 记录 LanceDB 迁移验证证据`.

## Risks and rollback surface

- LanceDB and PyArrow increase distribution size; the packaged probe provides feasibility evidence but final executable size remains a release trade-off.
- LanceDB API differences across versions require bounded dependency versions once the probe selects a working release.
- Vector data is derived and rebuildable, so rollback consists of reverting code/config and recreating the old backend; no LanceDB-to-Milvus data migration is promised.
- A failed vector-store or embedding initialization must leave core chat available with RAG disabled.
