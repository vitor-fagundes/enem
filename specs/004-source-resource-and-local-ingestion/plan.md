# Implementation Plan: Source Resource and Local Ingestion Contract

**Branch**: `004-source-resource-and-local-ingestion` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-source-resource-and-local-ingestion/spec.md`

## Summary

Implement the SPEC-004 first-increment contract: a Python CLI and library that ingests local files and ZIP members into content-addressed raw storage with SHA-256 deduplication, records operational metadata in SQLite (SourceResource, ResourceAcquisition, IngestionRun), and provides serializable SourceLocator and EvidenceReference contracts for future domain layers. Single-writer, sequential execution, no parsers, no HTTP, no domain interpretation.

## Technical Context

**Language/Version**: Python 3.12 (pinned in `.python-version`; managed by `uv` with frozen `uv.lock`)

**Primary Dependencies**: Python stdlib only for ingestion core — `sqlite3`, `hashlib`, `zipfile`, `pathlib`, `json`, `tempfile`, `os`, `fcntl`, `stat`. Existing project dependencies (`polars`, `duckdb`, `pytest`, `ruff`) remain unchanged. No new third-party dependencies required.

**Storage**: SQLite for operational metadata (`sqlite3` stdlib); local filesystem for immutable raw resource payloads under `data/raw/resources/<sha256>/payload`

**Testing**: `pytest` (existing, via `uv.lock`). Tests in `tests/python/`. Synthetic fixtures only; no real datasets.

**Target Platform**: Linux local (single-user, WSL2-compatible)

**Build Model**: The repository uses `[tool.uv] package = false` in `pyproject.toml`. The project is not pip-installed into the virtual environment. Source code is made importable by `pytest` via the `pythonpath` setting in `[tool.pytest.ini_options]`; this mechanism applies only during test execution, not to general `python -m` invocation. CLI execution requires explicit `PYTHONPATH` (see Project Structure).

**SQLite**: The `sqlite3` stdlib module links against the platform's SQLite library; the bundled version varies by Python build and operating system. This plan requires only standard SQL, `PRAGMA foreign_keys = ON`, and CHECK constraints — features available since SQLite 3.6.19 (2009). No version-specific features are assumed or required. FK support is verified at connection time.

**Performance Goals**: Not applicable for first increment. Single-file ingestion with streaming hash. Files up to configurable limit.

**Constraints**: Single-writer execution; no parallel processing; no distributed architecture; no LLM/OCR; stdlib-only for ingestion core; all tests use small synthetic fixtures.

**Scale/Scope**: Single user. First corpus target: ENEM 2017–2025 (~100 files max, not acquired in this increment). Tests use fixtures < 1 KB.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Spec is Source of Truth | PASS | All requirements traced to SPEC-004 spec.md FR-001–FR-021, INV-004-001–023. No requirements invented. |
| II. Scope Discipline | PASS | First increment only: local file, ZIP single-member, no HTTP, no parsers, no domain entities. Out-of-scope explicitly listed. |
| III. Simple Local-First | PASS | Python stdlib only. SQLite + filesystem. No new dependencies. No services, queues, or distributed coordination. Single-writer. |
| IV. Deterministic/Tested | PASS | SHA-256 deterministic. Each increment has corresponding test plan. Invariants tested. No LLM in ingestion. |
| V. Data Integrity/Provenance | PASS | SHA-256 on preserved bytes. Immutable raw. Acquisition metadata with nullable origin. No fabrication. Lineage recoverable via run/acquisition. |

No violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-source-resource-and-local-ingestion/
├── spec.md
├── plan.md                # This file
├── research.md            # Phase 0: technical decisions
├── data-model.md          # Phase 1: SQLite schema and entity design
├── quickstart.md          # Phase 1: validation guide
├── contracts/
│   ├── cli.md             # CLI interface contract
│   ├── locator.md         # SourceLocator serialization contract
│   └── evidence.md        # EvidenceReference serialization contract
└── checklists/
    └── requirements.md    # Existing quality checklist
```

### Source Code (repository root)

```text
packages/ingestion/
└── src/enem_rei_ingestion/
    ├── __init__.py        # Package init, version constant
    ├── __main__.py        # CLI entry point (argparse, dispatch)
    ├── db.py              # Schema creation, connection, FK enforcement, entity dataclasses
    ├── hasher.py          # Streaming SHA-256 with simultaneous copy
    ├── store.py           # Content-addressed storage, no-clobber publication, temp staging, input validation, orphan detection
    ├── ingest.py          # Orchestrator: run lifecycle, acquisition, dedup/revalidation, issue recording, report, recovery
    ├── zip_handler.py     # ZIP listing, safety validation, member materialization, limit enforcement
    └── contracts.py       # SourceLocator + EvidenceReference serialization/deserialization

tests/python/
├── test_analytics_stack.py    # Existing smoke test (unchanged)
├── conftest.py                # Shared fixtures: tmp dirs, synthetic files, DB setup
├── test_db.py                 # Schema, FK constraints, dataclass round-trip
├── test_hasher.py             # Streaming SHA-256 correctness
├── test_store.py              # Storage, no-clobber publication, temp management, input validation
├── test_ingest.py             # Run lifecycle, acquisition, dedup, issues, report, recovery
├── test_zip.py                # ZIP listing, materialization, security, limits, partial failures
├── test_contracts.py          # Locator + evidence round-trip, fixtures, media type
└── test_cli.py                # End-to-end CLI integration
```

**Build and Execution**:
- `pyproject.toml` uses `[tool.uv] package = false`. The project is not installed as a Python package.
- **Tests**: Extend `[tool.pytest.ini_options] pythonpath` to `["packages/analytics/src", "packages/ingestion/src"]`. This makes `enem_rei_ingestion` importable during pytest execution. This is the same mechanism already used for `enem_rei_analytics`.
- **CLI**: The `__main__.py` module provides the entry point. Invoke with explicit `PYTHONPATH`:
  ```
  PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion <command> [options]
  ```
  No `[project.scripts]` entry is required. No changes to `[tool.uv] package = false`.
- No new third-party dependencies are added to `uv.lock`.

**Module Consolidation Rationale**: 8 source modules (including `__init__.py` and `__main__.py`) and 7 new test files (plus `conftest.py` and existing `test_analytics_stack.py`). Consolidations:
- `models.py` absorbed into `db.py` — dataclasses are thin and tightly coupled to schema.
- `resource.py` + `acquisition.py` + `run.py` + `report.py` + `recovery.py` absorbed into `ingest.py` — these are aspects of the orchestration flow, not independent services.
- `publish.py` + `storage.py` + `security.py` consolidated into `store.py` — publication, content-addressed storage and input validation are one responsibility.
- `locator.py` + `evidence.py` consolidated into `contracts.py` — both are pure serialization contracts with no runtime dependencies on each other or on the ingestion pipeline.

## Incremental Implementation Sequence

### Increment 1: Schema, Models and Streaming Hash
**FR coverage**: FR-001 (entity separation), FR-002 (SourceResource fields), FR-019 (SQLite authority, physical model)
**Invariants**: INV-004-001, INV-004-002, INV-004-022

- SQLite schema creation: `source_resource`, `resource_acquisition`, `ingestion_run`, `ingestion_issue` tables with all columns, types, CHECK constraints and FK enforcement (`PRAGMA foreign_keys = ON`)
- Entity dataclasses: SourceResource, ResourceAcquisition, IngestionRun, IngestionIssue with field-level validation
- Streaming SHA-256 hasher: simultaneous copy-and-hash in single read pass, with byte counting and configurable limit enforcement (FR-015 step 3)
- Verify FK support at connection time; fail explicitly if unavailable
- **Tests**: Schema validation, FK constraint enforcement, CHECK constraints (status values, acquisition methods), SHA-256 uniqueness, hasher correctness on known inputs, hasher on empty file, hasher limit interruption
- **No acceptance cases claimed**: These are internal primitives; no operational ingestion exposed

### Increment 2: Content-Addressed Storage and Publication Protocol
**FR coverage**: FR-006 (input/storage safety), FR-015 (publication protocol steps 2–5), FR-016 (no-overwrite guarantee), FR-017 (temp cleanup under exclusivity)
**Invariants**: INV-004-003, INV-004-012, INV-004-015

- Single-writer exclusion via `fcntl.flock(LOCK_EX | LOCK_NB)` on `<data_root>/.ingestion.lock`; fail immediately if lock unavailable. This coordinates cooperating ingestion processes; it does not restrict unrelated processes from modifying the filesystem (FR-017)
- Input validation: open with `os.open(path, O_RDONLY | O_NOFOLLOW)` to atomically reject symlinks at the final path component; `os.fstat(fd)` on opened descriptor to verify regular file via `stat.S_ISREG()`; wrap fd with `os.fdopen()` for streaming read. Single operation eliminates TOCTOU window between check and open (FR-006)
- Storage directory anchor: at startup, resolve data root once with `os.path.realpath()` and open with `os.open(resolved_root, O_RDONLY | O_DIRECTORY)` to obtain a trusted directory fd. Walk `raw/resources/` by opening each component relative to its parent fd with `os.open(name, O_RDONLY | O_DIRECTORY | O_NOFOLLOW, dir_fd=parent_fd)` — `O_NOFOLLOW` atomically rejects symlinks at each path component. Create SHA-256 subdirectory with `os.mkdir(sha256_hex, dir_fd=resources_fd)` and open it the same way. The resulting chain of directory fds eliminates path-based resolution after initialization and detects symlinks at each component at point of use regardless of who placed them. However, `dir_fd` does not prevent a process with write access from relocating a real directory between operations — an open fd continues to reference the original inode even if moved outside the data root. Trust assumption: the data root and its controlled directory tree must be writable only by trusted processes. `fcntl.flock` coordinates cooperating ingestion writers but does not restrict unrelated filesystem access. Protection from untrusted concurrent modification is a deployment responsibility enforced through filesystem permissions, not a runtime guarantee provided by the ingestion process
- Temp file staging: create with `os.open(tmp_name, O_WRONLY | O_CREAT | O_EXCL, mode, dir_fd=resources_fd)` using `.tmp.<run_id>.<random>` naming; same filesystem as destination guaranteed by shared parent fd. SHA-256 is not required before copy begins — the temp file name is independent of content hash
- Content-addressed destination: `<data_root>/raw/resources/<sha256>/payload`, derived after copy-and-hash completes. The `<sha256>/` directory is created and opened via dir_fd-relative calls as described above
- No-clobber publication: `os.link(tmp_name, "payload", src_dir_fd=resources_fd, dst_dir_fd=sha256_fd)` atomically creates hard link and fails with `FileExistsError` if destination exists; followed by `os.unlink(tmp_name, dir_fd=resources_fd)`. All storage write operations use dir_fd-relative calls — no path-based resolution after the initial data root anchor. This replaces `os.rename()`, which silently overwrites existing destinations on Linux (FR-016)
- Orphan temp detection: with writer exclusivity confirmed, list `.tmp.*` files in storage directory; clean those not belonging to current run, logging each removal (FR-017)
- **Tests**: No-clobber (verify existing payload not overwritten), no-clobber on race (link fails cleanly), temp staging and cleanup, input rejection (symlinks via O_NOFOLLOW, directories, pipes, non-existent), dir_fd path component safety (symlink at intermediate directory rejected by O_NOFOLLOW + dir_fd), immutability of published payload
- **No acceptance cases claimed**: Storage primitives are independently testable but do not constitute a complete ingestion operation; run lifecycle, acquisition recording and SQLite commit are not yet present

### Increment 3: Complete Local File Ingestion
**FR coverage**: FR-003 (acquisition), FR-004 (timestamps), FR-011 (run lifecycle), FR-012 (SUCCESS/FAILED), FR-013 (issues/report), FR-014 (lineage), FR-015 (steps 1–7 complete), FR-016 (reuse with revalidation), FR-017 (abandoned run recovery, orphan reconciliation)
**Invariants**: INV-004-004, INV-004-005, INV-004-006, INV-004-007, INV-004-008, INV-004-009, INV-004-010, INV-004-011, INV-004-013

- Run lifecycle: create run identity before input validation (FR-011); status transitions RUNNING → SUCCESS | FAILED; finalization with `finished_at` and structured results. If SQLite is unavailable for run creation, abort with FATAL diagnostic — no payload published (FR-011, SC-009)
- Complete FR-015 pipeline integration: (1) create run, acquire single-writer lock → (2) open and validate input via Increment 2 primitives → (3) streaming copy+hash to temp via Increment 1 hasher → (4) validate temp hash/size → (5) check dedup: if destination exists, apply FR-016 reuse; otherwise publish via no-clobber link → (6) register resource + acquisition in SQLite transaction; only after commit is the unit announced as completed (SC-009) → (7) finalize run status and report
- Deduplication with revalidation: on existing destination, recalculate SHA-256 and verify byte_size of stored payload before reuse; divergence (including same-size corruption) → ERROR, no overwrite, no auto-correction of expected metadata (FR-016)
- Acquisition recording: `LOCAL_FILE` method with all nullable fields (`source_url`, `provider`, `source_definition_id`, `received_filename`, `source_retrieved_at`); new acquisitions never delete existing ones (FR-003)
- Issue recording: nullable `resource_id` for pre-resource failures; `input_reference` identifies the failing entry (FR-013, INV-004-011)
- Report generation: `resources_seen`, `resources_created`, `resources_reused`, `resources_failed`, per-unit results; report reflects SQLite state (FR-013, FR-019)
- Recovery: identify abandoned RUNNING runs, finalize as FAILED with recovery timestamp and cause; reconcile orphan payloads on explicit re-ingestion — verify integrity, register in current transaction if intact, fail without overwrite if divergent (FR-017)
- **Tests**: Case A (new file ingestion), Case B (re-ingestion/reuse), Case C (same path different content), Case D (same bytes different origins), Case G (corrupted payload detection), Case O (non-existent input), Case Q (origin altered during read), Case R (interrupted write/recovery, orphan reconciliation)
- **First increment claiming acceptance cases**: the complete publication protocol, run lifecycle, acquisition recording, SQLite commit and integrity checks are all in place before any operation is reported as successful

### Increment 4: ZIP Handling and Partial Failures
**FR coverage**: FR-007 (ZIP cardinality), FR-008 (raw/interim/processed), FR-012 (PARTIAL status), FR-018 (ZIP security and limits)
**Invariants**: INV-004-014, INV-004-015, INV-004-016, INV-004-017, INV-004-018

- ZIP preservation: ingest ZIP file as resource with own acquisition using Increment 3 pipeline; open preserved ZIP raw for listing/materialization via file object (not path) to maintain input validation guarantees
- Safe listing: enumerate members from preserved ZIP raw without creating resources; apply `max_zip_members` limit; present unsafe/duplicate entries as unseletable with warnings (FR-018)
- Safety validation: reject selection/materialization when name contains traversal (`..`), absolute path, root/separator escapes; entry is symlink/link/special; exact name appears more than once; decompression method unavailable. Destination derives from content hash, never from member name (FR-018, INV-004-015, INV-004-016)
- Single member materialization: decompress selected member to temp with streaming hash via Increment 1 hasher; enforce `max_member_uncompressed_bytes` and `max_total_uncompressed_bytes` during decompression; publish/deduplicate as separate resource via Increment 2 store
- Acquisition with `CONTAINER_MEMBER` method: `parent_resource_id` = ZIP resource, `container_locator` = exact member name; both fields NOT NULL for this method (FR-003, FR-007)
- PARTIAL status: ZIP operation with member materialization has multiple units (preserve ZIP + materialize member); at least one success + at least one failure without structural failure = PARTIAL (FR-012, SC-006). Listing without materialization that succeeds is SUCCESS, not PARTIAL
- Configurable limits: `max_input_bytes`, `max_zip_members`, `max_member_uncompressed_bytes`, `max_total_uncompressed_bytes` with finite defaults; registered in run parameters; verified during streaming read, not only from ZIP-announced sizes (FR-018, INV-004-017)
- **Tests**: Case E (ZIP+member materialization), Case F (traversal rejection), Case J (partial: ZIP preserved but member fails), Case M (same member from two ZIPs), Case N (direct file + container member same content), Case S (absolute path/links rejection), Case T (duplicate names rejection), Case U (limit enforcement at boundary and above), Case X (no recursive extraction of nested ZIP)

### Increment 5: Serialization Contracts and Auxiliary
**FR coverage**: FR-005 (fixtures), FR-009 (SourceLocator), FR-010 (EvidenceReference), FR-020 (supersession), FR-021 (media type)
**Invariants**: INV-004-019, INV-004-020, INV-004-021

- SourceLocator: dataclass with serialization/deserialization for 6 types (DOCUMENT, PDF_PAGE, CSV_ROW, ZIP_MEMBER, SHEET_RANGE, JSON_POINTER); round-trip validation; type-specific value schemas per [contracts/locator.md](contracts/locator.md); unknown types rejected (FR-009)
- EvidenceReference: dataclass with `locator` (SourceLocator), `evidence_role` (6 roles), nullable `notes`; resource identified solely by `locator.resource_id` — no duplicate `resource_id` at root; structural validation only, no automatic generation from acquisition (FR-010, INV-004-020)
- Fixture support: `acquisition_method = FIXTURE`, `fixture_kind` (SYNTHETIC, DERIVED_FROM_REAL); no fabrication of official provider/URL/catalog; member extracted from fixture ZIP preserves fixture nature in acquisition (FR-005)
- Basic media type: nullable `media_type` on SourceResource; file extension is auxiliary evidence, not authoritative; unknown content preserved with `media_type = null` and successful ingestion (FR-021)
- Supersession: new version with different bytes creates separate resource; no automatic supersession mechanism; `observed_at`/`source_retrieved_at` do not prove replacement; deferred per FR-020
- **Tests**: Case H (PDF evidence reference, zero-based page_index), Case I (conflicting evidence preserved without resolution), Case K (fixture identification, SYNTHETIC and DERIVED_FROM_REAL), Case L (supersession semantics, no auto-replacement), Case P (unknown media type, success with null), Case V (locator round-trip for all 6 types, including CSV parser_config and JSON_POINTER tokens)

### Increment 6: CLI Entry Point and End-to-End Integration
**FR coverage**: All FRs end-to-end
**Invariants**: All INV-004-nnn

- CLI entry point via `__main__.py`: argument parsing with `argparse` (stdlib)
- Subcommands per [contracts/cli.md](contracts/cli.md): `ingest` (local file, with `--zip-member`/`--list-members` options), `verify` (integrity check), `report` (export run)
- Exit codes: 0 (SUCCESS), 1 (PARTIAL), 2 (FAILED), 3 (FATAL)
- JSON report on stdout, human-readable summary on stderr
- Invocation: `PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion <command> [options]`
- **Tests**: CLI argument parsing, exit code mapping, JSON output format, representative end-to-end scenarios via CLI subprocess invocation; Case W (manifest reflects SQLite, lineage recoverable, single-writer enforced, report command exports run)

## Technical Risks and Decisions

| Risk/Decision | Impact | Mitigation |
|---------------|--------|------------|
| **No-clobber publication on Linux** | `os.rename()` silently overwrites existing destination on Linux, violating FR-016 immutability | Use `os.link(temp, dest)` + `os.unlink(temp)`. `os.link()` atomically fails with `FileExistsError` if destination exists. Same-filesystem requirement preserved by staging temp in `<data_root>/raw/resources/`. |
| **Input symlink TOCTOU** | Sequential `Path.is_file()` + `Path.is_symlink()` is vulnerable to race condition between check and open | Open with `os.open(path, O_RDONLY \| O_NOFOLLOW)` to atomically reject symlinks at final path component. Then `os.fstat(fd)` to verify `stat.S_ISREG()`. Wrap with `os.fdopen(fd)`. Single operation, no race window. |
| **Destination directory safety** | Symlink in controlled directory could redirect payload outside data root; `os.makedirs()` followed by `os.path.realpath()` has a TOCTOU window between creation and verification | Resolve data root once at startup, open as directory fd. Walk path components using `os.open(name, O_RDONLY \| O_DIRECTORY \| O_NOFOLLOW, dir_fd=parent_fd)` — symlinks rejected at each component at point of use. Create subdirectories with `os.mkdir(name, dir_fd=parent_fd)`. All file operations use `dir_fd`-relative calls, eliminating path-based resolution. `O_NOFOLLOW` detects symlinks regardless of who placed them, but does not prevent a process with write access from relocating a real directory between operations. Trust assumption: data root directory tree is writable only by trusted processes; filesystem permissions enforce this, not `fcntl.flock`. |
| **Single-writer exclusion** | Concurrent ingestion runs could corrupt state | Use `fcntl.flock(LOCK_EX \| LOCK_NB)` on `<data_root>/.ingestion.lock`. Fail immediately if lock unavailable. Coordinates cooperating ingestion processes only; does not restrict unrelated filesystem access. Document limitation. |
| **Hard link across filesystems** | `os.link()` fails across filesystem boundaries | Stage temp files in `<data_root>/raw/resources/` (same directory tree as destination). Error explicitly if cross-filesystem detected. |
| **ZIP decompression attacks** | Large uncompressed payloads could exhaust resources | Enforce `max_member_uncompressed_bytes` and `max_total_uncompressed_bytes` during streaming decompression by counting bytes written. Interrupt, clean temp, and register issue on exceed. Verify during read, not only from ZIP-announced sizes. |
| **SQLite version portability** | Python's `sqlite3` links against platform SQLite; version varies by build and OS | Require only standard SQL, `PRAGMA foreign_keys`, and CHECK constraints (available since SQLite 3.6.19, 2009). No version-specific features. Verify FK enforcement at connection time with a test query. |
| **CLI with `package = false`** | `python -m enem_rei_ingestion` requires package on `sys.path`; pytest `pythonpath` only applies during test runs, not CLI invocation | Tests: extend pytest `pythonpath` to include `"packages/ingestion/src"`. CLI: invoke with explicit `PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion`. No changes to build model. |
| **Filesystem + SQLite transaction window** | Payload published via `os.link()` but process dies before SQLite `COMMIT` leaves orphan | Documented as known window per FR-017. Orphan payload without SQLite record is detectable, never consumed as valid resource. Re-ingestion of same bytes verifies orphan integrity and reconciles in current transaction. |
