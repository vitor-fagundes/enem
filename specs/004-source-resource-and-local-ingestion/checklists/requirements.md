# Specification Quality Checklist: Source Resource and Local Ingestion Contract

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-10
**Feature**: [spec.md](../spec.md)
**Total items**: 50 (Content Quality 4 + Requirement Completeness 8 + Feature Readiness 4 + Semantic Preservation 27 + Boundary Respect 7)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on ingestion contract and provenance needs
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
- [x] Feature meets measurable outcomes defined in Success Criteria (success criteria validate first-increment contract capabilities, not full application implementation)
- [x] No implementation details leak into specification

## Semantic Preservation

- [x] All legacy sections (§1–§25) have corresponding requirements or sections
- [x] Objective and entity separation (§1) preserved (FR-001, Scope Boundaries)
- [x] Approved scope of first increment (§2) preserved (Scope Boundaries)
- [x] Field conventions and catalog (§3) preserved (Scope Boundaries)
- [x] SourceResource with SHA-256 identity, deduplication and all field semantics (§4) fully preserved (FR-002)
- [x] ResourceAcquisition with all fields, methods, parent/member and nullable semantics (§5) fully preserved (FR-003)
- [x] Timestamps, absence of origin, SPEC-002 specialization and fixtures (§6) preserved (FR-004, FR-005)
- [x] Input paths and storage with safety requirements (§7) preserved (FR-006)
- [x] ZIP and container cardinality including single-member, listing and recursive prohibition (§8) preserved (FR-007)
- [x] Raw/interim/processed separation and immutability (§9) preserved (FR-008)
- [x] SourceLocator contract with all six types, conventions and parser_config (§10) preserved (FR-009)
- [x] EvidenceReference contract with roles, non-duplication, no automatic generation and divergence preservation (§11) preserved (FR-010)
- [x] IngestionRun with units, identity-before-validation, FATAL handling and single run per invocation (§12) preserved (FR-011)
- [x] Status/severity with RUNNING/SUCCESS/PARTIAL/FAILED and INFO/WARNING/ERROR/FATAL (§13) preserved (FR-012)
- [x] IngestionIssue and report with counters, reconciliation and null resource_id (§14) preserved (FR-013)
- [x] Lineage, determinism, idempotency and exact deduplication (§15) preserved (FR-014)
- [x] Publication protocol with streaming hash, controlled destination and atomic SQLite commit (§16) preserved (FR-015)
- [x] Reuse and integrity divergence with full revalidation (§17) preserved (FR-016)
- [x] Recovery, single writer, orphans and abandoned runs (§18) preserved (FR-017)
- [x] ZIP security with traversal, links, duplicates, limits and streaming (§19) preserved (FR-018); all four configurable limit parameters preserved
- [x] Manifest, physical model and SQLite authority (§20) preserved (FR-019); model table layout preserved
- [x] Retifications and supersession with explicit evidence and no auto-propagation (§21) preserved (FR-020)
- [x] Media type, Git exclusions and incomplete sources (§22) preserved (FR-021)
- [x] All 23 invariants (§23 INV-004-001–INV-004-023) preserved integrally in Domain Invariants table
- [x] All 24 conceptual test cases (§24 Cases A–X) mapped to user story scenarios or edge cases
- [x] Completion criteria and consistency check (§25) mapped to success criteria (SC-001–SC-017) and migration acceptance (MA-001–MA-003)
- [x] Bloqueios resolvidos (§25) captured in the approved contract language of the FRs that address each blocker (B1→FR-001–FR-003/FR-007, B2→FR-003–FR-005, B3→FR-007–FR-008, B4→FR-009–FR-010, B5→FR-011–FR-014, B6→FR-015–FR-018)

## Boundary Respect

- [x] Does not redefine SPEC-001 Product Foundation requirements
- [x] Does not redefine SPEC-002 data governance entities or policies; documents approved specialization (FR-004)
- [x] Does not redefine SPEC-003 question domain model entities; does not create Question, QuestionPlacement or AnswerKeyObservation
- [x] Does not introduce implementation details (migrations, ETL, schema, UI)
- [x] Clearly identifies scope boundaries with adjacent specs
- [x] Does not introduce distributed architecture, parallel processing or multiple writers
- [x] Does not anticipate parsers, OCR, LLM, HTTP download or domain interpretation

## Notes

- Validation iteration 1: all 50 checklist items passed on initial migration.
- Validation iteration 2: all 50 checklist items revalidated after SC-006 and SC-009 corrections. All items still pass. Specific verifications:
  - SC-006 now matches FR-012 and Case J: structural failure can require FAILED even when earlier units completed individually. FR-012 states "Falha estrutural prevalece na classificação final"; SC-006 now includes "quando falha estrutural inviabiliza a execução como um todo, mesmo que unidades anteriores tenham sido concluídas individualmente."
  - SC-009 now matches FR-011 (FATAL when SQLite unavailable for run registration), FR-015 (publication protocol with streaming hash, controlled destination and metadata commit gate), FR-017 (orphan recovery without fabricating origin or past acquisition) and Case R (interrupted write and recovery). SC-009 distinguishes three scenarios: pre-run SQLite failure aborts before payload; post-filesystem/pre-commit failure leaves orphan; unit completion requires metadata commit.
  - All 23 invariants (INV-004-001–INV-004-023) remain preserved integrally in the Domain Invariants table.
  - All 24 acceptance cases (A–X) remain mapped to user story scenarios or edge cases without change.
  - No new business requirements were introduced by the SC-006/SC-009 corrections; the corrected language restores alignment with FR-011, FR-012, FR-015 and FR-017 which already contained these obligations.
  - The specification documents the contract, not completed implementation; the Measurable Outcomes header and the Migration Provenance both state this explicitly.
- The specification was reconstructed retrospectively from `specs/004-source-resource-and-local-ingestion.md`; the legacy file remains unchanged.
- Cases A–X from legacy §24 are distributed across User Stories 1–4 and edge cases as follows: Case A → US1-S1, Case B → US1-S2, Case C → Edge, Case D → US1-S3, Case E → US2-S1, Case F → Edge, Case G → US3-S3, Case H → US4-S1, Case I → US4-S3, Case J → US3-S1, Case K → Edge, Case L → Edge, Case M → US2-S2, Case N → US2-S3, Case O → Edge, Case P → Edge, Case Q → Edge, Case R → US3-S2, Case S → Edge, Case T → Edge, Case U → Edge, Case V → US4-S2, Case W → Edge, Case X → Edge.
- FR-004 preserves the approved SPEC-002 §9 specialization for local ingestion: `source_url`, `provider` and `source_definition_id` nullable when unknown; `observed_at` distinct from `source_retrieved_at`; documenting absence is valid, fabrication is not.
- FR-019 preserves the SQLite-as-authority model and expected physical table layout from legacy §20 without prescribing column names or ID strategies.
- The six resolved blockers (B1–B6) from legacy §25 are not separate requirements; they are addressed by the contracts in the functional requirements that resolve each concern.
- Three Migration Acceptance criteria (MA-001–MA-003) verify: zero new requirements, all 23 invariants preserved, all 24 conceptual test cases mapped.
- Success criteria (SC-001–SC-017) validate first-increment contract capabilities; they do not claim or verify completed application implementation.
- No new business requirements were introduced.
- This migration creates documentation only and does not claim the described ingestion contract is fully implemented.
