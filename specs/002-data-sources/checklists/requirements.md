# Specification Quality Checklist: Data Sources and Provenance

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-10
**Feature**: [spec.md](../spec.md)
**Total items**: 35 (Content Quality 4 + Requirement Completeness 8 + Feature Readiness 4 + Semantic Preservation 14 + Boundary Respect 5)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on data governance and policy needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Semantic Preservation

- [x] All legacy sections (§1–§22) have corresponding requirements
- [x] Source hierarchy (Tier A–D) fully preserved (FR-001–FR-005)
- [x] Source catalog (DS-001–DS-005) fully preserved (FR-006)
- [x] Immutability and raw/interim/processed separation preserved; provider-based layout illustrative (FR-007–FR-008)
- [x] Manifest and hash requirements preserved with approved SPEC-004 specialization (FR-009–FR-010)
- [x] Lineage and reproducibility preserved (FR-011–FR-012)
- [x] Temporal validity rules preserved (FR-013)
- [x] Taxonomy separation preserved (FR-014)
- [x] Classification confidence and versioning preserved (FR-015)
- [x] Frequency and recency policies preserved (FR-016–FR-017)
- [x] Quality report requirements preserved (FR-018)
- [x] Null semantics and date conventions preserved (FR-019–FR-020)
- [x] Security requirements preserved (FR-021)
- [x] Legacy acceptance criteria (§22) mapped to measurable success criteria (SC-001–SC-010)

## Boundary Respect

- [x] Does not redefine SPEC-003 question domain model entities
- [x] Does not redefine SPEC-004 ingestion contract details
- [x] Does not modify SPEC-001 Product Foundation requirements
- [x] Clearly identifies scope boundaries with adjacent specs
- [x] FR-014 references SPEC-003 §18 for detailed taxonomy cardinality without duplicating it

## Notes

- Validation iteration 1: all 35 checklist items passed on initial migration.
- Validation iteration 2: all 35 checklist items revalidated after provenance and storage-layout corrections. Two Semantic Preservation item descriptions updated to reflect the corrections; all items still pass.
- The specification was reconstructed retrospectively from `specs/002-data-sources.md`; the legacy file remains unchanged.
- FR-009: the legacy §9 manifest requirement listed `source_id`, `provider`, `source_url`, `retrieved_at` and `sha256` as unconditionally mandatory. SPEC-004 §5–6 explicitly specializes this for local ingestion: `sha256` (on the resource) and `observed_at` (on the acquisition) are unconditionally mandatory; `source_id`, `provider` and `source_url` are mandatory when known and applicable but nullable when unknown or inapplicable; `source_retrieved_at` is distinct from `observed_at` and records prior remote collection only when reliably known. FR-009 now preserves the legacy provenance intent with this approved specialization. No field that is actually known and applicable was made optional.
- FR-008: the legacy §8 provider-based directory tree is preserved as an illustrative layout. The `raw/interim/processed` separation remains mandatory. SPEC-004 §7 permits content-addressed storage under `raw/resources/`; FR-008 now allows either scheme (or other documented layouts) provided provider and catalog information remain recoverable through acquisition metadata.
- FR-014 preserves the legacy §13 requirement for "um tópico principal" and qualifies it with "no conjunto temático completo" to align with the approved refinement in SPEC-003 §18. No new business rule was introduced; the refinement was already approved by the product owner and recorded in SPEC-003.
- No new business requirements were introduced.
- This migration creates documentation only and does not claim the described data governance policies are fully implemented.
