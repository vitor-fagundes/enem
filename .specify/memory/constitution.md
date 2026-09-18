# enem-rei Constitution

## Core Principles

### I. Specification Is the Source of Truth
Agents and contributors MUST read every relevant specification in full before changing code.
Only requirements explicitly present in an approved specification may be implemented; future
capabilities MUST NOT be anticipated. A business-rule change MUST first be recorded in the
applicable specification, and architectural decisions MUST be recorded before implementation.
Ambiguities, contradictions, risks, and missing acceptance criteria MUST be reported and resolved
or documented as future questions rather than answered through an improvised product decision.

Rationale: implementation remains reviewable only when product intent and recorded decisions
precede code.

### II. Scope Discipline and Study Value
Every increment MUST stay within its declared scope and MUST have a reasonable path to improving
ENEM preparation before the exam. Technical interest alone is not sufficient justification.
When sophistication conflicts with learning velocity, learning velocity MUST prevail. Work outside
the current scope MUST be deferred explicitly rather than partially implemented.

Rationale: the project exists to allocate scarce study time, not to maximize software surface area.

### III. Simple, Local-First Architecture
The project MUST use the simplest architecture that satisfies the approved requirements. For the
current single-user product, solutions MUST remain local-first wherever applicable. Every material
architectural change MUST have documented justification before adoption.

Rationale: a small, explicit architecture reduces delivery cost while documented decisions keep
material changes reviewable.

### IV. Deterministic and Tested Domain Rules
Quantitative calculations and other deterministic rules MUST be reproducible and MUST NOT depend
on an LLM. LLM output MUST NOT be treated as a source of truth. Every implemented business rule
MUST have tests covering its invariants, relevant edge cases, and specified acceptance criteria.
Tests MUST exercise contract boundaries where persistence, transformations, or external-data
representations can invalidate those rules.

Rationale: recommendations and metrics must be auditable, repeatable, and safe to change.

### V. Data Integrity, Provenance, and Security
External and derived data MUST preserve origin, hashes where required, versions, transformation
parameters, and recoverable lineage. Files in `data/raw` are immutable: corrections MUST create a
new artifact or version and MUST NOT overwrite an original. Official sources take precedence as
defined by the specifications, and official facts, derived statistics, secondary material, and AI
inferences MUST remain distinguishable. Secrets MUST NOT enter source control, datasets, or public
manifests; environment variables MUST be used instead.

Rationale: trustworthy decisions require evidence whose origin, integrity, and transformation
history can be verified.

## Specification-Driven Development Workflow

1. Read the applicable specifications and identify their scope, invariants, and acceptance
   criteria before editing implementation files.
2. Record blocking ambiguities and product decisions in the specification; record architectural
   decisions in an ADR before implementation.
3. Implement only the approved increment, keep domain rules out of UI code, and preserve existing
   data and unrelated user changes.
4. Add proportionate tests for new or changed behavior, including business invariants and edge
   cases. Use synthetic or small fixtures instead of real large datasets.
5. Use the committed lockfiles. Dependency changes MUST be intentional, justified by the increment,
   and reflected in the relevant lockfile.
6. Before declaring completion, run every repository-defined validation relevant to the change.
7. Report each validation result and any environmental or product blocker. Every skipped or failing
   required validation MUST be disclosed and MUST NOT be represented as passing.

## Governance

This constitution governs engineering process and project-wide constraints. Product specifications
remain authoritative for business behavior; where a lower-level practice conflicts with this
constitution, the constitution governs the process and the conflict MUST be resolved in writing
before implementation.

Amendments require an explicit edit to this file, a rationale, an impact review against active
specifications and ADRs, and any necessary migration or follow-up plan. The Sync Impact Report for
an amendment is review material and MUST be removed before commit after its claims are verified.

Constitution versions follow semantic versioning: MAJOR for removal or incompatible redefinition
of governance, MINOR for a new principle or materially expanded obligation, and PATCH for
clarifications that do not change obligations. The ratification date records the initial adoption;
the last-amended date changes whenever normative content changes.

Every plan and implementation review MUST verify constitutional compliance before work begins and
before completion is declared. Reviewers MUST confirm specification coverage, scope discipline,
tests, data provenance and immutability where applicable, intentional dependency changes, and the
reported validation evidence. An exception that would violate a constitutional principle requires
an approved constitution amendment. Feature-specific or architectural exceptions that remain
compliant with every constitutional principle MAY instead be documented and approved in the
applicable specification and/or ADR. Undocumented exceptions are non-compliant.

**Version**: 1.0.0 | **Ratified**: 2026-09-18 | **Last Amended**: 2026-09-18
