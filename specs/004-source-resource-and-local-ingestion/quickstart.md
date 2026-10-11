# Quickstart Validation Guide: Source Resource and Local Ingestion

**Feature**: 004-source-resource-and-local-ingestion | **Spec**: [spec.md](spec.md)

## Prerequisites

- Python 3.12 (pinned in `.python-version`)
- `uv` package manager with frozen `uv.lock`
- Repository cloned and dependencies synced: `uv sync --frozen`

## Running Tests

```bash
# All Python tests (includes ingestion + existing analytics smoke test)
uv run --frozen pytest

# Ingestion tests only (all 7 test files)
uv run --frozen pytest tests/python/test_db.py tests/python/test_hasher.py \
  tests/python/test_store.py tests/python/test_ingest.py \
  tests/python/test_zip.py tests/python/test_contracts.py \
  tests/python/test_cli.py -v

# Linting and formatting
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

## Validation Scenarios

Each scenario maps to a SPEC-004 acceptance case. All use synthetic fixtures (< 1 KB). No real datasets required.

### Scenario 1: New File Ingestion (Case A)

```bash
# Create a synthetic test file
echo "test content for ingestion" > /tmp/test_input.txt

# Ingest it
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion ingest /tmp/test_input.txt \
  --data-root /tmp/test_data

# Expected: exit 0, JSON report with resources_created=1
# Verify: payload exists at raw/resources/<sha256>/payload
# Verify: SHA-256 matches independently computed hash
# Verify: SQLite contains resource + acquisition + run records
```

### Scenario 2: Re-Ingestion / Deduplication (Case B)

```bash
# Ingest same file again
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion ingest /tmp/test_input.txt \
  --data-root /tmp/test_data

# Expected: exit 0, resources_reused=1, resources_created=0
# Verify: still one resource in DB, now two acquisitions and two runs
# Verify: payload was revalidated (hash + size checked)
```

### Scenario 3: ZIP with Member Materialization (Case E)

```bash
# Create a synthetic ZIP
python3 -c "
import zipfile, io
with zipfile.ZipFile('/tmp/test.zip', 'w') as z:
    z.writestr('data.csv', 'col1,col2\n1,2\n')
    z.writestr('readme.txt', 'hello')
"

# List members
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion ingest /tmp/test.zip \
  --data-root /tmp/test_data --list-members

# Expected: exit 0, lists data.csv and readme.txt, no resources created for members

# Materialize one member
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion ingest /tmp/test.zip \
  --data-root /tmp/test_data --zip-member data.csv

# Expected: exit 0, ZIP resource + member resource created
# Verify: member has its own SHA-256 of decompressed bytes
# Verify: member acquisition has parent_resource_id = ZIP resource
```

### Scenario 4: ZIP Traversal Rejection (Case F)

```bash
# Create ZIP with path traversal
python3 -c "
import zipfile
with zipfile.ZipFile('/tmp/evil.zip', 'w') as z:
    z.writestr('../../etc/passwd', 'fake')
"

# Attempt to materialize the dangerous member
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion ingest /tmp/evil.zip \
  --data-root /tmp/test_data --zip-member '../../etc/passwd'

# Expected: exit 2 (FAILED), issue with ERROR severity
# Verify: no file written outside controlled directory
```

### Scenario 5: Corrupted Payload Detection (Case G)

```bash
# Ingest a file, then corrupt the stored payload
# Re-ingest the same content

# Expected: exit 2 (FAILED), explicit error
# Verify: no silent reuse, no overwrite, no metadata correction
```

### Scenario 6: Locator Round-Trip (Case V)

```bash
# Run the serialization contract tests (locator + evidence)
uv run --frozen pytest tests/python/test_contracts.py -v

# Validates: all 6 locator types serialize and deserialize without loss
# Validates: PDF uses zero-based page_index
# Validates: CSV preserves parser_config
# Validates: JSON_POINTER preserves tokens
# Validates: EvidenceReference round-trip with all 6 roles
```

### Scenario 7: Integrity Verification

```bash
# After ingestion, verify a resource
PYTHONPATH=packages/ingestion/src uv run python -m enem_rei_ingestion verify <sha256> --data-root /tmp/test_data

# Expected: reports MATCH or DIVERGENCE with details
```

## Full Acceptance Suite

The 24 acceptance cases (A–X) from SPEC-004 are distributed across test files by domain responsibility:

- `test_ingest.py` — Cases A, B, C, D, G, O, Q, R (local file ingestion, dedup, recovery)
- `test_zip.py` — Cases E, F, J, M, N, S, T, U, X (ZIP handling, partial failures, security)
- `test_contracts.py` — Cases H, I, K, L, P, V (locator, evidence, fixtures, media type)
- `test_cli.py` — Case W (end-to-end CLI, manifest, lineage)

Run all acceptance cases:

```bash
uv run --frozen pytest tests/python/test_ingest.py tests/python/test_zip.py \
  tests/python/test_contracts.py tests/python/test_cli.py -v
```

Each test case is tagged with its SPEC-004 case letter for traceability.

## Validation Checklist

- [ ] `uv run --frozen pytest` — all tests pass
- [ ] `uv run --frozen ruff check .` — no lint errors
- [ ] `uv run --frozen ruff format --check .` — formatting correct
- [ ] Exit codes match SPEC-004 status semantics (0/1/2/3)
- [ ] No payload written outside controlled `data/raw/resources/` directory
- [ ] SHA-256 computed during copy, not in separate read
- [ ] Reuse validates existing payload before accepting
- [ ] Corrupted payload causes explicit failure, not silent reuse
- [ ] Single-writer lock prevents concurrent execution
- [ ] ZIP traversal and unsafe entries rejected
- [ ] Configurable limits enforced during streaming read
- [ ] Orphaned payloads detected but not silently consumed
- [ ] Abandoned RUNNING runs identified and finalized as FAILED
- [ ] No third-party dependencies added beyond Python stdlib
- [ ] Existing tests (`test_analytics_stack.py`) still pass
