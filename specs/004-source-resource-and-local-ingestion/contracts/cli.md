# CLI Contract: Ingestion Commands

**Feature**: 004-source-resource-and-local-ingestion | **Spec**: [spec.md](../spec.md)

## Invocation

The repository uses `[tool.uv] package = false`. The ingestion package is not pip-installed. CLI invocation requires explicit `PYTHONPATH`:

```bash
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion <command> [options]
```

The entry point is `packages/ingestion/src/enem_rei_ingestion/__main__.py`.

## Commands

### `ingest` — Ingest a local file

```bash
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion ingest <input_path> [options]
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--data-root` | path | `data/` | Base directory for raw storage and DB |
| `--db` | path | `<data_root>/ingestion.db` | SQLite database path |
| `--source-id` | string | null | Source catalog ID (e.g., DS-003) |
| `--source-url` | string | null | Known source URL |
| `--provider` | string | null | Known provider name |
| `--source-retrieved-at` | ISO 8601 | null | Known remote retrieval timestamp |
| `--fixture-kind` | SYNTHETIC\|DERIVED_FROM_REAL | null | Fixture identification |
| `--zip-member` | string | null | Exact member name to materialize from ZIP |
| `--list-members` | flag | false | List ZIP members without materializing |
| `--max-input-bytes` | integer | config default | Max bytes to read from input |
| `--max-zip-members` | integer | config default | Max ZIP entries to list |
| `--max-member-uncompressed-bytes` | integer | config default | Max decompressed bytes per member |
| `--max-total-uncompressed-bytes` | integer | config default | Max total decompressed bytes |

**Behavior**:
- Without `--list-members` or `--zip-member`: ingest as single local file.
- With `--list-members`: preserve ZIP, list members, no materialization.
- With `--zip-member <name>`: preserve ZIP, list, materialize selected member.
- `--list-members` and `--zip-member` are mutually valid in the same invocation (list then materialize).
- A single invocation = one IngestionRun. At most one input file and one ZIP member.

### `verify` — Verify integrity of a stored resource

```bash
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion verify <resource_id_or_sha256> [--data-root ...]
```

Recomputes SHA-256 and byte size from the stored payload and compares with the SQLite record. Reports match or divergence.

### `report` — Export run report

```bash
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion report <run_id> [--data-root ...] [--format json|text]
```

Exports the run's metadata, status, unit results, resources, acquisitions, issues and counters.

## Output Format

All commands produce a JSON report on stdout. Human-readable summary on stderr.

### Report Schema (stdout)

```json
{
  "run_id": "<uuid>",
  "status": "SUCCESS | PARTIAL | FAILED",
  "started_at": "<ISO 8601>",
  "finished_at": "<ISO 8601>",
  "pipeline_name": "enem_rei_ingestion",
  "pipeline_version": "<version>",
  "parameters": { ... },
  "resources_seen": 1,
  "resources_created": 1,
  "resources_reused": 0,
  "resources_failed": 0,
  "units": [
    {
      "name": "preserve_input",
      "status": "SUCCESS",
      "resource_id": "<id>",
      "sha256": "<hex>",
      "byte_size": 12345
    }
  ],
  "acquisitions": [ ... ],
  "issues": [ ... ]
}
```

## Exit Codes

| Code | Meaning | SPEC-004 Reference |
|------|---------|-------------------|
| 0 | SUCCESS — all requested units completed | FR-012 |
| 1 | PARTIAL — at least one unit succeeded, at least one failed | FR-012 |
| 2 | FAILED — no reliable output produced | FR-012 |
| 3 | FATAL — execution infrastructure failure (e.g., DB unavailable) | FR-011, FR-012 |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENEM_DATA_ROOT` | `data/` | Base directory for storage and database |
| `ENEM_INGESTION_DB` | `<data_root>/ingestion.db` | Override SQLite database path |
