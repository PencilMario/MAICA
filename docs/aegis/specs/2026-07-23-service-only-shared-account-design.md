# Service-only shared account design

## Intent

Merge `upstream/main` while retaining the fork's disabled GitHub Actions policy, then redefine `SERVICE_ONLY` as a trusted local-deployment mode. In that mode every caller is authenticated as one shared local account, independently of the supplied token.

## Baseline

- Upstream authentication owner: `maica/maica_utils/users_utils.py`, specifically `FscUsersFuncMixin.login`.
- Upstream persistence owner: SQLAlchemy `SqlUser` through `DatabaseUtils.SessionAuth`.
- The deleted `account_utils.py` and its pool-based authentication path are retired and must not remain as a fallback.
- `SERVICE_ONLY=0` retains upstream authentication behavior.

## Behavior

When `G.A.SERVICE_ONLY == "1"`:

1. Authentication selects the fixed username `service_only` before decoding or validating credentials.
2. Any token value, including absent, empty, malformed, or otherwise invalid input, is accepted.
3. Password checks, email-confirmation checks, suspension checks, and Fail2Ban are bypassed.
4. If the shared user does not exist, it is created once with:
   - username `service_only`;
   - nickname `Service Only`;
   - email `service_only@localhost.local`;
   - confirmed email state;
   - a random bcrypt password hash that is not derived from client input.
5. Concurrent first logins converge on the same unique user row; a uniqueness race is recovered by querying the winning row.
6. The shared user's identity is assigned to `maica_settings.verification`, so all local clients share the same `user_id` and associated data.
7. Existing WebSocket connection-replacement semantics continue to apply after identity assignment unless tests show that upstream treats them as part of credential validation rather than session ownership.

## Merge policy

- `.github/workflows/maica.yml`: use upstream workflow structure, retain `workflow_dispatch` only, and disable every job with `if: ${{ false }}`.
- `maica/initializer/gen_keys.py`: use the upstream `cryptography` implementation.
- `maica/maica_http.py`: use upstream.
- `maica/maica_nows.py`: use upstream.
- `maica/maica_utils/account_utils.py`: accept upstream deletion.

## Tests

Tests must first fail against the upstream authentication implementation, then prove:

- malformed or absent tokens authenticate as the shared account in service-only mode;
- repeated logins reuse one account;
- creation produces the fixed confirmed identity and an unusable random password hash;
- a simulated uniqueness race converges on the existing account;
- normal mode still rejects malformed credentials through the upstream path.

Related upstream authentication and database tests must also pass. Workflow syntax and unresolved merge markers must be checked separately.

## Non-goals

- Configurable service-only username or profile fields.
- Per-token or per-caller accounts.
- Preserving the former automatic-registration implementation.
- Making service-only mode suitable for remotely exposed or multi-user deployments.

## Impact and compatibility

The behavior is intentionally insecure outside a trusted local deployment. The canonical owner remains `FscUsersFuncMixin.login`; no duplicate authentication owner or compatibility fallback is introduced. Normal deployments are unaffected while `SERVICE_ONLY` is disabled.

