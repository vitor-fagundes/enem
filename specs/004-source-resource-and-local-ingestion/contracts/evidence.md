# Contract: EvidenceReference Serialization

**Feature**: 004-source-resource-and-local-ingestion | **Spec**: [spec.md](../spec.md) FR-010

## Structure

```json
{
  "locator": {
    "resource_id": "<string>",
    "locator_type": "<string>",
    "locator_value": { ... }
  },
  "evidence_role": "<string>",
  "notes": "<string or null>"
}
```

The resource is identified solely by `locator.resource_id`. There is no separate `resource_id` field at the root of the reference (INV-004-019, FR-010).

## Evidence Roles

| Role | Semantics | SPEC-004 Reference |
|------|-----------|-------------------|
| `CONTENT` | Resource contains question/item content | FR-010 |
| `PLACEMENT` | Resource contains placement/positioning evidence | FR-010 |
| `ANSWER_KEY` | Resource contains answer key information | FR-010 |
| `EXTERNAL_IDENTIFIER` | Resource contains external identifier evidence | FR-010 |
| `OFFICIAL_ASSOCIATION` | Resource contains evidence of official question-skill association | FR-010 |
| `PUBLICATION_METADATA` | Resource contains publication metadata | FR-010 |

## Semantic Rules

1. **No automatic generation**: Ingesting a resource does not create EvidenceReferences. References are created by interpretation layers (domain specs), not by acquisition (FR-010, INV-004-020).

2. **Official does not mean official**: Preserving a resource from an official source does not make all interpretations official. `OFFICIAL_ASSOCIATION` requires specific evidence of the association, per SPEC-003 (FR-010).

3. **Multiple evidence per fact**: A single domain fact may have multiple EvidenceReferences from different resources (FR-010).

4. **Multiple facts per resource**: A single resource may support evidence for many different domain facts (FR-010).

5. **Divergence preservation**: Conflicting evidence must be preserved by the layers that identify it. Ingestion does not detect or resolve semantic conflicts (FR-010).

6. **Precision honesty**: When only the resource is known, use `DOCUMENT` locator type. Do not fabricate page/row precision (FR-010).

7. **Ownership**: The reference is attached to the observation/fact that the interpreting layer produces. No generic `entity_type`, `entity_id`, `field_name` or `fact_id` schema (FR-010).

## Storage

EvidenceReferences are not stored in an ingestion table. They are serialized as JSON within domain-layer structures created by future specs. The ingestion contract defines the serialization format and validates structural correctness.

## Validation Rules

1. `locator` must be a valid SourceLocator (see [locator.md](locator.md)).
2. `evidence_role` must be one of the six defined roles.
3. `notes` is nullable.
4. Serialization and deserialization must round-trip without loss.
5. The first increment validates the contract structurally; it does not create, store or interpret evidence references in the ingestion layer.
