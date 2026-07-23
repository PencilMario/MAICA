# Service-only Shared Account Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use aegis:subagent-driven-development (recommended) or aegis:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge upstream and make `SERVICE_ONLY=1` authenticate every caller as one persistent local shared account.

**Architecture:** Resolve structural conflicts in favor of upstream, except for the fork's disabled Actions policy. Add one service-only branch at the canonical authentication owner, backed by the upstream SQLAlchemy auth session and a fixed `SqlUser` identity.

**Tech Stack:** Python 3.12+, asyncio, SQLAlchemy async ORM, bcrypt, pytest, GitHub Actions YAML.

**Baseline / Authority Refs:** `docs/aegis/specs/2026-07-23-service-only-shared-account-design.md`; user-approved conflict policy; upstream `FscUsersFuncMixin.login` contract.

**Compatibility Boundary:** `SERVICE_ONLY=0` keeps upstream token, password, email, suspension, Fail2Ban, and WebSocket ownership behavior. No deleted pool-based authentication path remains active.

**Verification:** Target pytest coverage, related upstream authentication/database tests, Ruff on changed Python files, conflict-marker scan, YAML parse, and clean unmerged-index check.

---

### Task 1: Resolve upstream merge structure

**Files:**
- Modify: `.github/workflows/maica.yml`
- Replace from upstream: `maica/initializer/gen_keys.py`
- Replace from upstream: `maica/maica_http.py`
- Replace from upstream: `maica/maica_nows.py`
- Delete per upstream: `maica/maica_utils/account_utils.py`

**Why this task exists:** Apply the approved ownership decisions before adding behavior to the new upstream architecture.

**Impact / Compatibility:** Upstream owns runtime implementations; the fork retains only its deliberate CI and release-disable policy.

**Repair Track:** Resolve textual and modify/delete conflicts at their new canonical owners.

**Retirement Track:** Retire `account_utils.py` and old NoWs/image implementations; do not retain compatibility fallbacks.

**Verification:** `git diff --name-only --diff-filter=U` must be empty after staging.

- [ ] Accept upstream versions for the four runtime conflict files and upstream deletion of `account_utils.py`.
- [ ] Rebuild `maica.yml` from upstream with `workflow_dispatch` and `if: ${{ false }}` on every job.
- [ ] Stage resolutions and verify no unmerged paths remain.

### Task 2: Specify service-only behavior with failing tests

**Files:**
- Delete: `tests/test_account_serviceonly.py`
- Create: `tests/test_service_only_auth.py`

**Why this task exists:** Protect unconditional shared-account login while demonstrating that the upstream implementation does not yet provide it.

**Impact / Compatibility:** Tests call the real `FscUsersFuncMixin` with isolated async SQLite auth storage or narrowly controlled session fixtures; they do not preserve the deleted pool API.

**Verification:** `python -m pytest tests/test_service_only_auth.py -q` must fail because service-only bypass is absent.

- [ ] Add a test where malformed and absent tokens both assign username `service_only` and the same user ID.
- [ ] Add a test proving the first login creates exactly one confirmed shared row with a bcrypt hash unrelated to token input.
- [ ] Add a repeated-login test proving the same row is reused.
- [ ] Add a normal-mode regression test proving malformed tokens are rejected.
- [ ] Run the target file and record the expected RED failure.

### Task 3: Implement the canonical shared-account branch

**Files:**
- Modify: `maica/maica_utils/users_utils.py`

**Why this task exists:** Make local service-only deployments independent of official credential issuance without creating multiple user identities.

**Impact / Compatibility:** The branch executes before token decoding only when `G.A.SERVICE_ONLY == "1"`; normal mode remains unchanged.

**Repair Track:** Add a private shared-user lookup/create helper using `DatabaseUtils.SessionAuth`, fixed profile fields, random bcrypt input, commit, and uniqueness-race retry.

**Retirement Track:** The former token-derived auto-registration behavior and `AccountCursor` owner remain deleted.

**Verification:** Target service-only tests pass, followed by related authentication/database tests.

- [ ] Implement fixed shared-user lookup and one-time creation.
- [ ] Catch `sqlalchemy.exc.IntegrityError` from concurrent creation and reload the winning row.
- [ ] Branch before token parsing and bypass credential/account-state checks in service-only mode.
- [ ] Assign the shared identity through the existing verification object and preserve downstream WebSocket ownership handling.
- [ ] Run `python -m pytest tests/test_service_only_auth.py -q` and confirm GREEN.

### Task 4: Regression and merge verification

**Files:**
- Modify if required by verified failures only: tests or changed authentication owner.
- Record: `docs/aegis/work/2026-07-23-service-only-merge/50-evidence.md`

**Why this task exists:** Prove the merge is mechanically resolved and the authentication contract works without masking upstream regressions.

**Impact / Compatibility:** Verification covers the new branch, normal auth boundary, runtime syntax, workflow structure, and Git merge state.

**Verification:**
- `python -m pytest tests/test_service_only_auth.py tests/test_database_and_sessions.py tests/test_shutdown_and_release.py -q`
- `python -m ruff check maica/maica_utils/users_utils.py tests/test_service_only_auth.py`
- `python -m compileall -q maica`
- `rg -n "^(<<<<<<<|=======|>>>>>>>)" . --glob '!docs/aegis/**'`
- `git diff --name-only --diff-filter=U`

- [ ] Run target and related regression tests.
- [ ] Run Ruff and compilation checks.
- [ ] Parse or otherwise validate the workflow and confirm every job is disabled.
- [ ] Confirm no conflict markers or unmerged index entries remain.
- [ ] Write exact commands, outputs, residual risks, and confidence to the evidence record.
- [ ] Create the merge commit only after all required checks have passed or bounded failures are reported.

