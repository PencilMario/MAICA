# LanceDB vector store evidence

## Source verification

- `python -m pytest tests/test_vector_store.py tests/test_http_and_images.py -q`
  passed: 8 tests.
- Running the suite after setting the existing test baseline
  `G.A.MCORE_GENERIC = "0"` passed: 45 tests.
- `python examples/lancedb_nuitka_probe.py <temporary-path>` printed
  `LANCEDB_PROBE_OK` on two consecutive processes using the same external
  database directory.
- LanceDB 0.34.0 and PyArrow 25.0.0 were tested on CPython 3.13.7 / Windows 11.

## Nuitka verification

- The full `build_local.ps1 -UseZig` run exited zero after 2,213 seconds and
  produced `build/maica_starter.exe` (306.82 MiB) and
  `build/create_account.exe` (9.49 MiB).
- Running `build/maica_starter.exe -t print` failed before application startup:
  `dns.rdtypes.ANY.URI` could not import the standard-library `struct` module.
  This confirms the build script's file-existence check is insufficient.
- Nuitka 4.0 with Zig 0.16.0 successfully compiled the probe as onefile.
- The resulting executable was 240,290,992 bytes.
- The executable failed during Python initialization before probe code ran:
  `dns.rdtypes.IN.KX` could not import the `dns` package.
- Rebuilding with `--include-package=dns` reproduced the same initialization
  failure. This rules out a simple missing-module collection flag.
- Rebuilding the probe with both `--include-package=dns` and
  `--include-module=struct` also failed before application startup, reporting
  that `dns.rdtypes.IN.KX` could not import the top-level `dns` package. The
  ineffective flags were not retained in `build_local.ps1`.
- LanceDB 0.25 and later, including 0.34, depend on `lance-namespace`; 0.24.3
  lacks a Windows wheel. Therefore version pinning cannot remove that network
  stack while retaining a supported Windows binary.

## Conclusion

The embedded LanceDB implementation and ordinary Windows Python runtime are
verified. A Nuitka 4.0 / CPython 3.13 onefile artifact is not currently
runtime-ready because LanceDB's mandatory namespace dependency conflicts with
Nuitka initialization. The build script does not retain the ineffective
`--include-package=dns` workaround. Re-test with a future Nuitka/LanceDB
release or package the application in standalone mode before claiming onefile
support.

## Existing test-environment issue

Running `pytest -q` from a process that has not initialized MAICA configuration
leaves `G.A.MCORE_GENERIC` as an empty string and causes two unrelated tests to
fail while converting it with `int()`. Initializing that existing baseline to
`"0"` produces 45 passing tests. This task does not change that unrelated
configuration behavior.
