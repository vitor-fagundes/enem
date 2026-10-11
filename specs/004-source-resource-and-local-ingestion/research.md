# Research: Source Resource and Local Ingestion Contract

**Feature**: 004-source-resource-and-local-ingestion | **Date**: 2026-10-10

## R-001: Package Structure

**Decision**: Create `packages/ingestion/src/enem_rei_ingestion/` as a new Python package parallel to `packages/analytics/`. 8 source modules (including `__init__.py` and `__main__.py`): `db.py`, `hasher.py`, `store.py`, `ingest.py`, `zip_handler.py`, `contracts.py`.

**Rationale**: Ingestion (SPEC-004) and analytics (future specs) have different responsibilities and dependency profiles. Ingestion uses only Python stdlib; analytics uses polars/duckdb. Separation follows spec boundaries (SPEC-004 vs future analytics specs) and Constitution Principle II (Scope Discipline). The existing `pyproject.toml` uses `[tool.uv] package = false`, so the project is not pip-installed. For tests, extending `pythonpath` in `[tool.pytest.ini_options]` to include `"packages/ingestion/src"` makes the package importable during pytest execution. For CLI invocation, explicit `PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion` is required since pytest's `pythonpath` setting applies only during test runs, not to general `python -m` invocation.

**Alternatives considered**:
- *Embed within `packages/analytics/`*: Rejected because ingestion has no dependency on polars/duckdb and conflates distinct concerns.
- *Create as installable package*: Rejected as unnecessary complexity for single-user local execution. `uv run` with `pythonpath` is sufficient and matches existing convention.

## R-002: SQLite Schema Approach

**Decision**: Use Python `sqlite3` stdlib with explicit SQL `CREATE TABLE` statements managed in a `db.py` module. No ORM, no migration framework.

**Rationale**: The schema is small (3–4 tables), stable (defined by approved spec), and the single-writer constraint eliminates migration-concurrency concerns. The plan requires only standard SQL, `PRAGMA foreign_keys = ON`, and CHECK constraints — features available since SQLite 3.6.19 (2009). The `sqlite3` stdlib module links against the platform's SQLite library; the bundled version varies by Python build and OS. No version-specific features (JSON functions, strict mode) are assumed or required. FK support is verified at connection time. An ORM would add a dependency and an abstraction layer that Constitution Principle III prohibits without justification.

**Alternatives considered**:
- *SQLAlchemy/Peewee*: Rejected — adds third-party dependency for a 4-table schema. Constitution III: "simplest architecture that satisfies."
- *Drizzle (TypeScript side)*: Rejected — the ingestion runs in Python; the TypeScript Drizzle adapter serves the web app. These are separate operational databases.
- *Alembic migrations*: Rejected — no concurrent users, schema defined by spec, version-1 creation is a single script. Future schema changes can use simple version-checking in `db.py`.

## R-003: SHA-256 Streaming Implementation

**Decision**: Compute SHA-256 and count bytes in a single streaming pass during the copy operation. Use `hashlib.sha256()` with `read()`/`write()` in fixed-size chunks (64 KB default).

**Rationale**: FR-015 step 3 requires "Calcular SHA-256 e contar bytes durante a própria cópia." A single-pass approach satisfies this: read chunk → update hash → write chunk → accumulate size. This also enforces size limits during the read without loading the entire file.

**Alternatives considered**:
- *Hash after copy*: Rejected — FR-015 explicitly prohibits hashing in one read and copying in another.
- *Memory-mapped hash*: Rejected — loads entire file; FR-018 requires streaming ("MUST operar em streaming; MUST NOT carregar payload inteiro na memória").
- *Using `shutil.copyfileobj`*: Rejected — does not expose the chunk loop needed for simultaneous hashing and limit checking.

## R-004: Content-Addressed Storage Layout

**Decision**: Store raw payloads at `<data_root>/raw/resources/<full_sha256>/payload`. One directory per unique content hash. No subdirectory sharding in first increment.

**Rationale**: FR-006 suggests `raw/resources/<sha256>/payload` as "uma direção simples para implementação." Full SHA-256 hex (64 chars) as directory name is unique. No sharding needed at this scale (~100 files). The layout fits within `data/raw/` which is the approved raw storage location from SPEC-002.

**Alternatives considered**:
- *Shard by first 2 hex chars*: Premature optimization. At < 1000 resources, flat directory is sufficient. Can be added later without changing semantics.
- *Provider-based directories*: Illustrative layout from SPEC-002; FR-008 allows content-addressed storage as approved specialization.
- *Filename includes original name*: Rejected — FR-006 states "Nomes recebidos e nomes de membros MUST NOT controlar diretamente o caminho final."

## R-005: Single-Writer Exclusion

**Decision**: Use `fcntl.flock(fd, LOCK_EX | LOCK_NB)` on a dedicated lock file (`<data_root>/.ingestion.lock`). Fail immediately with clear error if lock cannot be acquired.

**Rationale**: FR-017 requires "impedir sobreposição de writers por mecanismo local simples de exclusividade/falha imediata." `fcntl.flock` is the simplest POSIX file locking mechanism, requires no external dependency, and fails immediately with `LOCK_NB`. The lock file is separate from the database to avoid SQLite-specific locking semantics. Note: `flock` coordinates cooperating ingestion processes only; it does not restrict unrelated filesystem access. Protection of the data root from untrusted concurrent modification is a deployment responsibility enforced through filesystem permissions.

**Alternatives considered**:
- *SQLite `BEGIN EXCLUSIVE`*: Only locks for the duration of the transaction, not the entire run. Insufficient for filesystem operations between transactions.
- *PID file*: Requires stale-PID detection logic; `flock` is automatically released on process termination.
- *Advisory lock on DB file*: Couples locking to DB availability; FR-011 requires run creation even when DB is failing (for FATAL reporting).

## R-006: Atomic No-Clobber Publication Protocol

**Decision**: Create temporary file via `os.open(tmp_name, O_WRONLY | O_CREAT | O_EXCL, mode, dir_fd=resources_fd)` in the storage directory. After hash validation, derive the content-addressed destination path (`<sha256>/payload`), create the SHA-256 subdirectory with `os.mkdir(sha256_hex, dir_fd=resources_fd)`, and publish with `os.link(tmp_name, "payload", src_dir_fd=resources_fd, dst_dir_fd=sha256_fd)` followed by `os.unlink(tmp_name, dir_fd=resources_fd)`. Then commit metadata in SQLite transaction.

**Rationale**: FR-015 requires publication on controlled destination without overwrite. On Linux, `os.rename()` silently overwrites existing destinations, violating FR-016. `os.link()` atomically fails with `FileExistsError` if the destination exists — true no-clobber on POSIX. All storage operations use `dir_fd`-relative calls anchored to a trusted directory fd opened at startup with `O_NOFOLLOW`, eliminating path-based resolution after initialization. By staging temp files under `<data_root>/raw/resources/`, same-filesystem is guaranteed for `os.link()`. The link-then-commit sequence means: if the process dies after link but before SQLite commit, the payload becomes an orphan detectable by FR-017 recovery. Input files are opened with `os.open(path, O_RDONLY | O_NOFOLLOW)` and verified via `os.fstat(fd)` to be regular files, eliminating the TOCTOU window of sequential `Path.is_file()` + `Path.is_symlink()` checks.

**Alternatives considered**:
- *`os.rename()`*: Atomic on POSIX but silently overwrites existing destination. Violates FR-016 no-clobber requirement. Rejected.
- *`shutil.move()`*: Falls back to copy+delete across filesystems; not atomic; also clobbers. Rejected.
- *Write directly to final path*: Risks partial writes visible as complete. Rejected.
- *Path-based `os.makedirs()` + `os.path.realpath()` verification*: TOCTOU window between directory creation and validation. Rejected in favor of `dir_fd`-relative operations.
- *Two-phase commit with filesystem*: Over-engineering for single-writer. Rejected per Constitution III.

## R-007: CLI Interface Design

**Decision**: Module-executable CLI via `__main__.py`, invoked with `PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion`. Subcommands via `argparse` (stdlib). Output as JSON on stdout with human-readable summary on stderr.

**Rationale**: The spec requires "relatório serializável" and "retorno de execução parcial/falha não pode parecer sucesso completo." `argparse` is stdlib, no dependency needed. Exit codes distinguish success (0), partial (1), failed (2), fatal (3). JSON output satisfies the serializable report requirement.

**Alternatives considered**:
- *`click`/`typer`*: Adds third-party dependency. Rejected per Constitution III.
- *Plain text output*: Does not satisfy "relatório serializável." Rejected.
- *No CLI (library only)*: The spec describes invocations and command output. A CLI is the natural interface for "execução local por comandos" (ADR-0001). Library API is also provided for testing.

## R-008: Temporary File Cleanup Safety

**Decision**: Temporary files use a `.tmp.` prefix in the target directory. On startup with exclusive lock confirmed, scan for and remove `.tmp.*` files, logging each removal. Never remove files without the `.tmp.` prefix.

**Rationale**: FR-017 states "Temporários nunca são recursos válidos. Com exclusividade de escrita confirmada, uma nova execução pode limpar temporários abandonados, registrando a ação." The `.tmp.` prefix ensures only ingestion-controlled temporaries are affected. The exclusive lock guarantees no other writer is active.

**Alternatives considered**:
- *OS temp directory*: Temp files must be on same filesystem as destination for `os.link()` publication. OS temp may be on a different filesystem.
- *No cleanup*: Accumulated temporaries waste space. FR-017 explicitly permits cleanup with exclusive lock.

## R-009: Ingestion Database Location

**Decision**: Default location: `<data_root>/ingestion.db`, configurable via `ENEM_INGESTION_DB` environment variable. The `data_root` itself defaults to `data/` relative to project root, configurable via `ENEM_DATA_ROOT`.

**Rationale**: The `.gitignore` pattern `*.db` already excludes database files. Placing the DB alongside the data it governs follows the principle of locality. Environment variables for configuration follow AGENTS.md rule 10 ("Use variáveis de ambiente"). The web app's Drizzle/SQLite DB remains separate in `apps/web/.local/`.

**Alternatives considered**:
- *Fixed path*: Breaks testability; tests need isolated temporary databases.
- *In `apps/web/.local/`*: Conflates ingestion metadata with web app data. Rejected.
- *XDG data directory*: Over-engineering for single-user local tool. Rejected.
