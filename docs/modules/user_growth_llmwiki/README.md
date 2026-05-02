# User growth + LLMwiki content reuse module

This v0 module is a structure mirror and growth-tracking layer for an already-existing Obsidian-style vault. It does not teach Obsidian, import an external wiki plugin, modify frozen NoeticBraid behavior, or bypass the existing Obsidian writer boundary.

## Boundary

The module reads explicitly approved fixture structure by default and returns metadata-only objects:

- `VaultProfile` describes folder shape, note metadata hints, internal-link hints, raw-user zones, AI-allowed zones, and structured risk flags.
- `LLMWikiSourceRecord` records immutable source identity with `record_id`, `origin`, `content_hash`, `layer`, and `ingested_at`. It stores hashes and provenance, not raw private note content.
- `StructureSuggestion`, `SideNoteCandidate`, `DigestionCandidate`, and `GrowthReportInput` are candidates for review. They do not write, rename, move, delete, normalize, or auto-tag user notes.
- `ContentReusePlan` separates source identity, compiled/wiki candidates, output candidates, and append-only log records.

Final file creation or append-only vault writes remain the responsibility of the existing Obsidian center/writer and its guardable approval boundary.

## Four-layer model

The module implements the LLMwiki-style separation as local structural behavior:

1. `raw/source`: immutable source records with content hashes and origin metadata.
2. `compiled/wiki`: NoeticBraid-owned synthesis candidates such as index or wiki concept drafts.
3. `output`: review packets and report inputs used by downstream daily, weekly, or monthly assembly.
4. `log`: append-only activity records for ingestion, compilation, output, user response, and audit events.

The four layers are represented in memory and may be persisted as metadata through the optional SQLite store. The store intentionally excludes raw note text, credential paths, browser state, token material, and machine-local paths.

## Scanner behavior

`VaultScanner` is read-only and defaults to `approved_fixtures_only=True`. In that mode the root must be listed in `VaultScanConfig.approved_fixture_roots` or contain the approval marker file `.noeticbraid_fixture_approved`; arbitrary directories are rejected before Markdown files are read. Future real-vault reading is isolated behind `RealVaultIntegrationBoundary`, which requires an explicit user-acknowledged contract.

For approved fixtures, the scanner walks folders and Markdown notes, parses only top-of-file frontmatter when present, collects wikilink and Markdown-link hints, infers note types from path/name/frontmatter, and marks raw-user or AI-allowed zones from explicit configuration, frontmatter, or fixture-safe heuristics.

Scanner risks are emitted as `RiskFlag` objects, for example `missing_index`, `missing_project_index`, `orphan_cluster`, `duplicate_topic_name`, `missing_frontmatter_template`, and `ambiguous_ai_zone`. Warnings are data that candidate generators can consume; the scanner itself never edits the filesystem.

## Candidate handoff

Candidate generation is deterministic for a fixed profile, source refs, and timestamp. Hypotheses and challenges are labelled in the claim text and are never represented as facts. Structure suggestions expose `to_writer_handoff_request()` for a guardable candidate-only packet; it contains `requires_review` and `no_user_original_mutation` flags so a downstream writer can enforce final review.

## External repository use

The implementation uses external LLMwiki/RAG repositories only as design pattern references: topic isolation, raw/source versus compiled/wiki versus output separation, `_index.md` navigation, source hashing, candidate review queues, append-only logs, ingestion/data-source separation, and lightweight local database posture. No external code is copied, vendored, cloned, installed, or embedded in this module.
