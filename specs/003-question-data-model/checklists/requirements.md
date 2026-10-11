# Specification Quality Checklist: Question Data Model

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-10
**Feature**: [spec.md](../spec.md)
**Total items**: 37 (Content Quality 4 + Requirement Completeness 8 + Feature Readiness 4 + Semantic Preservation 15 + Boundary Respect 6)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on domain model definition needs
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
- [x] Feature meets measurable outcomes defined in Success Criteria (success criteria validate conceptual model capabilities, not completed application implementation)
- [x] No implementation details leak into specification

## Semantic Preservation

- [x] All legacy sections (§1–§34) have corresponding requirements or sections
- [x] Exam structure entities (§3–§6) fully preserved (FR-001–FR-004)
- [x] Question identity, content revisions and deduplication policy (§7–§8) preserved (FR-005–FR-007); FR-006 includes revision-placement compatibility, alternatives/assets recoverability on referenced revision, and future attempt referenceability without defining Attempt
- [x] Placement, alternatives and label correspondence (§9–§11) preserved (FR-008–FR-010); FR-010 includes revision-placement compatibility, unambiguous label mapping within same presentation context and revision, and explicit preservation of divergences between resources
- [x] Answer key observations with annulment, rectification and supersession (§12) fully preserved (FR-011); includes internal resolution history preserved separately from official rectifications, publication-date vs acquisition-date distinction, supersedes_id scope restricted to official retification, and unknown/conflicting/unresolved situations excluded from automatic error correction
- [x] Assets with target, order and optional materialization (§13) fully preserved (FR-012)
- [x] Official taxonomy: competency and skill with versioned matrix (§14–§15) preserved (FR-013–FR-014)
- [x] Classification runs, QuestionSkill, Topic and QuestionTopic with approved cardinality reconciliation (§16–§18) preserved (FR-015–FR-018); FR-015 includes lineage references, batch-execution transparency, LLM-metadata centralization, and classification_version vs run_id vs set-identity distinction; FR-016 includes mandatory run reference for automatic classification, specific evidence for OFFICIAL associations independent of content source, review_status scope, and preservation of competing proposals; FR-018 includes set/run/procedure-version/taxonomy-version distinction, analytical-taxonomy clause, and no silent mixing of concurrent proposals
- [x] Auxiliary concepts: difficulty distinction and optional metadata (§19–§20) preserved (FR-019–FR-020)
- [x] Cross-cutting domain rules: content preservation, foreign language, annulment, partial data, provenance, state separation, preservation rules (§21–§27) preserved (FR-021–FR-027)
- [x] Conceptual model and domain/storage separation (§28–§29) preserved (FR-028–FR-029)
- [x] All 24 invariants (§30 INV-001–INV-024) preserved integrally in Domain Invariants table
- [x] All 10 conceptual test cases (§33 Cases A–J) mapped to user story acceptance scenarios
- [x] All 16 legacy acceptance criteria (§32) mapped to success criteria (SC-001–SC-016)
- [x] Field category convention (§2) preserved in Scope Boundaries table

## Boundary Respect

- [x] Does not redefine SPEC-002 data governance entities or policies
- [x] Does not redefine SPEC-004 ingestion contract details
- [x] Does not modify SPEC-001 Product Foundation requirements
- [x] Clearly identifies scope boundaries with adjacent specs
- [x] References SPEC-002 §13 cardinality and documents approved reconciliation in FR-018 without contradicting it
- [x] Does not introduce implementation details (migrations, ETL, schema, UI)

## Notes

- Validation iteration 1: all 37 checklist items passed on initial migration.
- Validation iteration 2: all 37 checklist items revalidated after contractual language restoration. Four Semantic Preservation item descriptions updated to reflect the restored contracts; one Feature Readiness item description updated to clarify success-criteria scope. All items still pass.
- The specification was reconstructed retrospectively from `specs/003-question-data-model.md`; the legacy file remains unchanged.
- Restored contracts cover six areas of domain obligation that were compressed during the initial migration:
  - **Content revision, placement and future attempt references** (FR-006): revision-placement compatibility restored; alternatives and assets on referenced revisions must remain recoverable; future attempts must be able to reference the exact revision presented, the corresponding alternative and the answer-key observation used, without defining or implementing Attempt.
  - **Alternative-label compatibility and ambiguity prevention** (FR-010): revision must be recoverable from the alternative and compatible with the placement's question; within the same presentation context and revision, a published label must not resolve ambiguously to distinct alternatives; divergences between resources must remain explicit.
  - **Answer-key resolution history versus official rectification** (FR-011): internal resolution history preserved separately from official rectifications; `published_at` must not receive the acquisition date as a substitute; `supersedes_id` must not be reused to simulate a nonexistent official publication; unknown, conflicting or unresolved situations must not authorize automatic error correction.
  - **ClassificationRun provenance and mandatory references** (FR-015): complete LLM metadata centralized in the run and referenced by associations; lineage references to inputs and revisions preserved; batch executions must identify their set transparently; execution identity distinguished from algorithm version; `classification_version` in associations does not substitute `classification_run_id` or set identity.
  - **Official association evidence and competing proposals** (FR-016): mandatory run reference for automatic classification; OFFICIAL associations require specific evidence of the association itself, which may differ from the content source; `review_status` records association review, never officiality; proposals, executions and prior reviews must remain traceable; changes must preserve the originating classification and run.
  - **Classification set, run and version distinctions** (FR-018): set, execution, procedure version and taxonomy version are distinct concepts; a single execution may classify multiple questions; competing proposals must coexist in distinct sets; the taxonomy remains analytical regardless of official evidence for a specific association; analysis must make sets and versions explicit without silently mixing concurrent proposals.
- FR-018 preserves the approved cardinality reconciliation from legacy §18: exactly one PRIMARY in a complete set, zero or one in a partial set, zero topics permitted for unclassified questions. This reconciliation was already approved by the product owner and recorded in the legacy SPEC-003. No new business rule was introduced.
- Cases A–J from legacy §33 are distributed across User Stories 1–4 as acceptance scenarios: Case A → US1-S1, Case B → US3-S1, Case C → US2-S2, Case D → US3-S2, Case E → US1-S2, Case F → US2-S1, Case G → US2-S3, Case H → US1-S3, Case I → US3-S3, Case J → US4-S1.
- Three Migration Acceptance criteria (MA-001–MA-003) verify: zero new requirements, all 24 invariants preserved, all 16 legacy acceptance criteria mapped.
- Success criteria (SC-001–SC-016) validate conceptual model capabilities — that the domain model can represent the required situations without loss of semantics. They do not claim or verify completed application implementation.
- No new business requirements were introduced.
- This migration creates documentation only and does not claim the described domain model is fully implemented.
