# Contract: SourceLocator Serialization

**Feature**: 004-source-resource-and-local-ingestion | **Spec**: [spec.md](../spec.md) FR-009

## Structure

```json
{
  "resource_id": "<string>",
  "locator_type": "<string>",
  "locator_value": { <type-specific object> }
}
```

Each locator has exactly one `resource_id` (INV-004-019). The `locator_type` determines the schema of `locator_value`.

## Type Schemas

### DOCUMENT

Refers to the entire resource. Does not imply that a more precise location has been determined.

```json
{
  "resource_id": "r-123",
  "locator_type": "DOCUMENT",
  "locator_value": {}
}
```

### PDF_PAGE

Physical page index, zero-based. This is the physical page in the PDF file, not the printed page number.

```json
{
  "resource_id": "r-123",
  "locator_type": "PDF_PAGE",
  "locator_value": {
    "page_index": 0
  }
}
```

- `page_index`: integer, ≥ 0.

### CSV_ROW

Logical record index after applying parser configuration. Zero-based, after header treatment.

```json
{
  "resource_id": "r-123",
  "locator_type": "CSV_ROW",
  "locator_value": {
    "record_index": 42,
    "parser_config": {
      "encoding": "utf-8",
      "delimiter": ";",
      "quoting": "minimal",
      "header": true,
      "skip_blank_lines": true
    }
  }
}
```

- `record_index`: integer, ≥ 0.
- `parser_config`: object — must be embedded or reference an immutable recoverable configuration. Identifies encoding, delimiter, quoting/escape rules, header treatment, and blank-line handling. The locator's logical meaning depends on this configuration.

### ZIP_MEMBER

Exact name of a member within a ZIP resource.

```json
{
  "resource_id": "r-zip-456",
  "locator_type": "ZIP_MEMBER",
  "locator_value": {
    "member_name": "provas/2024_CN_dia2.pdf"
  }
}
```

- `member_name`: string — the exact name as stored in the ZIP directory. Duplicate names make the locator ambiguous and are rejected.

### SHEET_RANGE

Cell range within a named sheet. Zero-based coordinates, start-inclusive, end-exclusive.

```json
{
  "resource_id": "r-123",
  "locator_type": "SHEET_RANGE",
  "locator_value": {
    "sheet_name": "Planilha1",
    "row_start": 1,
    "row_end": 100,
    "column_start": 0,
    "column_end": 5
  }
}
```

- All indices: integers, ≥ 0.
- `row_start < row_end`, `column_start < column_end` (non-empty ranges).

### JSON_POINTER

RFC 6901 JSON Pointer. Empty string refers to the entire document.

```json
{
  "resource_id": "r-123",
  "locator_type": "JSON_POINTER",
  "locator_value": {
    "pointer": "/data/items/0"
  }
}
```

- `pointer`: string — RFC 6901 semantics. Must not be interpreted as JSONPath.

## Validation Rules

1. `resource_id` is required and must be non-empty.
2. `locator_type` must be one of the six defined types.
3. `locator_value` must conform to the type-specific schema.
4. Serialization and deserialization must round-trip without loss.
5. The first increment validates and serializes the contracts; it operates on `DOCUMENT` and `ZIP_MEMBER` only. PDF, CSV, SHEET_RANGE and JSON_POINTER are validated structurally but not resolved.
6. Unknown types are rejected; future extensions require defined semantics.
