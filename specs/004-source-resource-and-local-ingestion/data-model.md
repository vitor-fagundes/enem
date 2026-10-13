# Data Model: Source Resource and Local Ingestion Contract

**Feature**: 004-source-resource-and-local-ingestion | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Overview

Four tables in a single SQLite database. SQLite is the sole authority for operational metadata (FR-019, INV-004-022). Payloads reside on the local filesystem under content-addressed paths.

## Tables

### `ingestion_run`

Exactly one run per invocation (FR-011, INV-004-008).

| Column | Type | Constraint | SPEC-004 Reference |
|--------|------|------------|-------------------|
| `id` | TEXT | PRIMARY KEY | FR-011 |
| `pipeline_name` | TEXT | NOT NULL | FR-011 |
| `pipeline_version` | TEXT | NOT NULL | FR-011 |
| `started_at` | TEXT | NOT NULL (ISO 8601 UTC) | FR-011 |
| `finished_at` | TEXT | NULL while RUNNING; NOT NULL on normal finalization | FR-011 |
| `status` | TEXT | NOT NULL; CHECK IN ('RUNNING','SUCCESS','PARTIAL','FAILED') | FR-012 |
| `parameters` | TEXT | NOT NULL (JSON; may be '{}') | FR-011 |
| `code_revision` | TEXT | NULL when unavailable | FR-011 |
| `results` | TEXT | NULL (JSON; unit results and lineage when applicable) | FR-011, FR-014 |

**Rules**:
- Run identity created before input validation (FR-011).
- `status` transitions: RUNNING → SUCCESS | PARTIAL | FAILED. No backward transitions.
- FATAL: if SQLite is unavailable, abort without publishing payload; emit diagnostic with allocated `id` to stderr (FR-011).
- `parameters` includes effective limits and options (FR-018).
- `results` captures `resources_seen`, `resources_created`, `resources_reused`, `resources_failed` and per-unit outcomes (FR-013).

### `source_resource`

Content identity by SHA-256 (FR-002, INV-004-001, INV-004-002).

| Column | Type | Constraint | SPEC-004 Reference |
|--------|------|------------|-------------------|
| `id` | TEXT | PRIMARY KEY | FR-002 |
| `sha256` | TEXT | NOT NULL, UNIQUE | FR-002 |
| `byte_size` | INTEGER | NOT NULL (≥ 0) | FR-002 |
| `media_type` | TEXT | NULL | FR-002 |
| `storage_locator` | TEXT | NOT NULL | FR-002 |
| `registered_at` | TEXT | NOT NULL (ISO 8601 UTC) | FR-002 |

**Rules**:
- `sha256` is the SHA-256 hex digest of the bytes effectively preserved (INV-004-002).
- `byte_size` includes zero for empty files (FR-002).
- `storage_locator` is relative to data root (e.g., `raw/resources/<sha256>/payload`) (FR-006).
- `registered_at` is set once on first registration; reutilization does not update it (FR-002).
- `media_type` is a basic MIME type when identifiable with confidence; NULL when unknown (FR-021).
- No origin context stored here: name, URL, provider, parent/member belong to acquisition (FR-002).

### `resource_acquisition`

Origin context per observation (FR-003, INV-004-005, INV-004-006).

| Column | Type | Constraint | SPEC-004 Reference |
|--------|------|------------|-------------------|
| `id` | TEXT | PRIMARY KEY | FR-003 |
| `resource_id` | TEXT | NOT NULL, FK → source_resource(id) | FR-003 |
| `ingestion_run_id` | TEXT | NOT NULL, FK → ingestion_run(id) | FR-003 |
| `acquisition_method` | TEXT | NOT NULL; CHECK IN ('LOCAL_FILE','CONTAINER_MEMBER','FIXTURE') | FR-003 |
| `observed_at` | TEXT | NOT NULL (ISO 8601 UTC) | FR-003, FR-004 |
| `source_definition_id` | TEXT | NULL | FR-003, FR-004 |
| `source_url` | TEXT | NULL | FR-003, FR-004 |
| `provider` | TEXT | NULL | FR-003, FR-004 |
| `received_filename` | TEXT | NULL | FR-003 |
| `parent_resource_id` | TEXT | NULL; FK → source_resource(id) when NOT NULL | FR-003, FR-007 |
| `container_locator` | TEXT | NULL; exact member name for CONTAINER_MEMBER | FR-003 |
| `source_retrieved_at` | TEXT | NULL | FR-004 |
| `fixture_kind` | TEXT | NULL; CHECK IN ('SYNTHETIC','DERIVED_FROM_REAL') WHEN NOT NULL | FR-005 |

**Rules**:
- `parent_resource_id` and `container_locator` are NOT NULL when `acquisition_method = 'CONTAINER_MEMBER'` (FR-003).
- `fixture_kind` is NOT NULL when `acquisition_method = 'FIXTURE'` (FR-005).
- `source_retrieved_at` is distinct from `observed_at`; never fabricated from `observed_at` (FR-004).
- New acquisitions never delete existing acquisitions (FR-003, INV-004-004).
- One acquisition per successful observation; no extras per internal step (FR-003).

### `ingestion_issue` (optional table)

Issues may alternatively be embedded as JSON in `ingestion_run.results` (FR-019). A separate table is used only if it improves operational clarity.

| Column | Type | Constraint | SPEC-004 Reference |
|--------|------|------------|-------------------|
| `id` | TEXT | PRIMARY KEY | FR-013 |
| `run_id` | TEXT | NOT NULL, FK → ingestion_run(id) | FR-013 |
| `stage` | TEXT | NOT NULL | FR-013 |
| `severity` | TEXT | NOT NULL; CHECK IN ('INFO','WARNING','ERROR','FATAL') | FR-012, FR-013 |
| `message` | TEXT | NOT NULL | FR-013 |
| `resource_id` | TEXT | NULL; FK → source_resource(id) when NOT NULL | FR-013 |
| `input_reference` | TEXT | NULL | FR-013 |
| `locator` | TEXT | NULL (JSON SourceLocator) | FR-013 |
| `exception_type` | TEXT | NULL | FR-013 |

**Rules**:
- `resource_id = NULL` allowed for failures before resource exists (INV-004-011).
- If `locator` and `resource_id` are both present, `locator.resource_id` must agree (FR-013).

## Serialized Contracts (JSON)

### SourceLocator

Stored as JSON in `ingestion_issue.locator` and in EvidenceReference structures. Not a table.

```json
{
  "resource_id": "<resource_id>",
  "locator_type": "DOCUMENT | PDF_PAGE | CSV_ROW | ZIP_MEMBER | SHEET_RANGE | JSON_POINTER",
  "locator_value": { ... }
}
```

See [contracts/locator.md](contracts/locator.md) for value schemas per type.

### EvidenceReference

Not stored in a table; serialized as JSON within domain-layer structures (future specs).

```json
{
  "locator": { <SourceLocator> },
  "evidence_role": "CONTENT | PLACEMENT | ANSWER_KEY | EXTERNAL_IDENTIFIER | OFFICIAL_ASSOCIATION | PUBLICATION_METADATA",
  "notes": "<nullable string>"
}
```

See [contracts/evidence.md](contracts/evidence.md) for role semantics.

## Relationships

```text
ingestion_run 1 ── N resource_acquisition
source_resource 1 ── 0..N resource_acquisition
source_resource 1 ── 0..N resource_acquisition (via parent_resource_id)
ingestion_run 1 ── 0..N ingestion_issue
source_resource 1 ── 0..N ingestion_issue (nullable FK)
```

## Integrity Constraints (enforced by SQLite)

1. `PRAGMA foreign_keys = ON` — all FKs enforced.
2. `source_resource.sha256` UNIQUE — no duplicate content identity.
3. `resource_acquisition.resource_id` FK → `source_resource.id` — no orphan acquisitions.
4. `resource_acquisition.ingestion_run_id` FK → `ingestion_run.id` — every acquisition has a run.
5. `resource_acquisition.parent_resource_id` FK → `source_resource.id` — parent must exist.
6. `ingestion_issue.run_id` FK → `ingestion_run.id` — every issue has a run.
7. `ingestion_issue.resource_id` FK → `source_resource.id` WHEN NOT NULL — resource must exist if referenced.

## State Diagram: IngestionRun Status

```text
[created] → RUNNING → SUCCESS   (all requested units completed)
                    → PARTIAL   (≥1 completed, ≥1 failed, no structural failure)
                    → FAILED    (no reliable output, or structural failure overrides)
```

Recovery: an abandoned RUNNING run is finalized as FAILED with recovery timestamp and cause (FR-017).

## Filesystem Layout

```text
<data_root>/
├── raw/
│   └── resources/
│       └── <sha256_hex>/
│           └── payload          # Immutable raw bytes
├── ingestion.db                 # SQLite operational metadata
└── .ingestion.lock              # Single-writer lock file
```

Temporary files during ingestion: `<data_root>/raw/resources/.tmp.<run_id>.<random>` — same filesystem as final destination for no-clobber hard link publication via `os.link()`.
