# Evidence

## TDD

- RED: `python -m pytest tests/test_service_only_auth.py -q` produced 3 expected service-only failures and 1 normal-mode pass because upstream attempted token decryption.
- GREEN: the same command produced `4 passed` after implementation.

## Target and related regression

- Command: `python -m pytest tests/test_service_only_auth.py tests/test_database_and_sessions.py::test_new_websocket_login_atomically_replaces_stale_session tests/test_shutdown_and_release.py::test_release_workflow_skips_an_existing_pypi_version -q`
- Result: `6 passed`, with one environment-level Requests dependency warning.

## Static and structural checks

- Ruff on the authentication owner and changed tests: passed.
- `python -m compileall -q -x "maica[\\/]Lib" maica`: passed.
- Workflow policy check: exactly five jobs contain `if: ${{ false }}` and only `workflow_dispatch` is configured.
- `git diff --name-only --diff-filter=U`: empty.

## Broader-suite boundary

A broader 16-test selection produced 13 passes and 3 failures. Two failures are upstream environment-baseline failures caused by `G.A.MCORE_GENERIC == ''`; the third was the upstream release assertion that conflicted with the explicitly approved disabled-workflow policy and was updated. These unrelated environment-dependent tests were not changed.

## Residual risk

- No live MySQL concurrency test was run; the shared-account uniqueness race is covered with concurrent SQLite sessions and explicit `IntegrityError` recovery.
- The complete application suite requires a fully initialized MAICA environment and was not used as the completion gate.

## Post-commit verification

- Target and related tests: `6 passed`.
- Ruff: passed.
- Source compilation: passed.
- Workflow policy: five jobs disabled.
- Conflict-marker scan: none in tracked source outside bundled dependencies.
- Git: clean merge commit with parents `50de3b2` and `0669557`; `upstream/main` is an ancestor of `HEAD`.
