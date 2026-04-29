# Stage 1.5 (B Freeze) Manifest

- contract_version: 1.0.0
- frozen: true
- authoritative: true
- generated_at: 2026-04-29T02:27:37Z (GPT-A freeze) + 2026-04-29 local-patch
- total_files_excluding_manifest: 91
- zip_sha256: see external `noeticbraid_phase1_1_freeze.zip.sha256` (anchors GPT-A's 90-file freeze zip; local PR commit adds 2 review summaries on top)
- stage1_input_files_carried_unchanged_in_main: 71 (originally 72 in GPT-A freeze zip; 1 local-patched: pyproject.toml)
- stage15_modified_files: 13 (12 by GPT-A: 3 docs/contracts/*.{py,md,yaml} + 6 docs/contracts/fixtures/*.json + 1 docs/contracts/fixtures/_README.md + 1 manifest.md + 1 packages/noeticbraid-core/src/noeticbraid_core/__init__.py; +1 by local PR patch: packages/noeticbraid-core/pyproject.toml)
- stage15_added_files: 8 (6 by GPT-A: 2 scripts/ + 1 .github/workflows/ + 1 docs/audit_trail.md + 2 docs/reviews/phase1.1/stage1_*; +2 by local PR patch: 2 docs/reviews/phase1.1/freeze_*)
- total_files_in_repo_after_freeze: 92 (= main 84 + added 8)
- stage1_implementation_commit: b8d7152
- stage1_review_claude: PASS (0D 0S)
- stage1_review_codex: PASS (0D 0S)
- freeze_review_claude: PASS (0D 0S, see docs/reviews/phase1.1/freeze_claude.md)
- freeze_review_codex: PARTIAL (0D 1S 1M 2L; S=PEP 440 patched locally; M=HealthResponse example patched locally; see docs/reviews/phase1.1/freeze_codex.md)

## Self-reference note

`manifest.md` is not included in its own SHA table (would be self-referential).
All other 89 files are listed below with exact SHA256. The zip-level integrity
is anchored by the external `noeticbraid_phase1_1_freeze.zip.sha256` sidecar.

## Local patches applied on top of GPT-A freeze zip

Two local patches were applied by the local main session before merging into `main`,
to address Codex review S/M findings that fall on GPT-A's blacklist (cannot be
fixed by GPT-A without v2 freeze):

1. `packages/noeticbraid-core/pyproject.toml`:
   `version = "0.1.0-stage0"` → `version = "0.1.0+stage0"` (PEP 440 local-version
   form; semantically equivalent; unblocks CI `pip install -e`).
2. `docs/contracts/phase1_1_openapi.yaml`:
   `HealthResponse.contract_version.example` 0.1.0 → 1.0.0;
   `HealthResponse.authoritative.example` false → true (align with frozen 1.0.0).

`.gitignore` carries the local-fix from noeticbraid initial commit b8d7152
(`private/**` + placeholder exceptions); the freeze zip's `.gitignore` (Stage 1
buggy form `private/`) was rejected during PR apply, since it would re-exclude
private/ placeholder READMEs.

## Source-of-truth

- Stage 1 implementation under packages/noeticbraid-core/src/noeticbraid_core/schemas/** = freeze source of truth, byte-identical to Stage 1 (commit b8d7152).
- Stage 1 tests under packages/noeticbraid-core/tests/** = byte-identical to Stage 1 (262 PASSED preserved).
- docs/contracts/phase1_1_pydantic_schemas.py = reverse-synced stub (bare types + Literal only; CONTRACT_NOTE comments capture all constraints).
- docs/contracts/phase1_1_api_contract.md = §20 frozen field constraint table appended.
- docs/contracts/phase1_1_openapi.yaml = components.schemas upgraded to authoritative full version.
- docs/contracts/fixtures/*.json = byte-content from packages/.../tests/fixtures/, only meta fields upgraded to authoritative + 1.0.0.

## File List

| 路径 | SHA256 | 字数 | 用途 | 状态 |
|---|---|---:|---|---|
| .editorconfig | 48bf56a6cd915c2528f22f05c6a709d296abaaef8664ec4bd641f134f4561f81 | 27 | unchanged from Stage 1 | unchanged |
| .github/workflows/ci.yml | bdc99a0c721edcda4f85c99020c6fc30b7fa9e9637627556762509959e377c72 | 275 | added: CI workflow | added |
| .gitignore | a96adf25f24708d523c903b2285a4b01ae0987a9e520f50d3c02f17ee379ba03 | 47 | local-fix (private/** + placeholder exceptions) applied at noeticbraid initial import b8d7152 | unchanged-from-main |
| LICENSE | 2dcba93cf6b0df20e714d4b20df5daaacbde7843353435c1f3538f68a4a0df78 | 1413 | unchanged from Stage 1 | unchanged |
| NOTICE | 1ec900193816f3206f0359a095e8d9e129eafc1b607e3f58852aa5caf54f18ae | 50 | unchanged from Stage 1 | unchanged |
| README.md | e5b85971da2a5711ca73d216ca791a2030c11b5c4da66bc74f86a5b871cb2cc8 | 232 | unchanged from Stage 1 | unchanged |
| docs/architecture/step3_authority.md | 4e4c39752baa88d1102527ba8373febede0b3b72859661cb5cb8ea3a03ecb807 | 115 | unchanged from Stage 1 | unchanged |
| docs/architecture/step4_authority.md | e4bc524754075fb95c1e024300e84a47cb5c996329ff66652f2c8d6fa3e98510 | 85 | unchanged from Stage 1 | unchanged |
| docs/architecture/step5_phase1_1_design.md | 138e523322289a11a2789b3323514add9315b53f2a3f2911daf1a32e5744ba38 | 2010 | unchanged from Stage 1 | unchanged |
| docs/audit_trail.md | 7bf6780dec5571647271221b8ac55d8d2b1475e549e50affdfd8c0caa9cb6d81 | 104 | added: append-only audit trail | added |
| docs/contracts/contract_change_requests/README.md | 2d40e068010b07349baed62bbac678a96a9cafd9ef59a15e8ff01afac6e8e8ed | 85 | unchanged from Stage 1 | unchanged |
| docs/contracts/contract_change_requests/_template.md | 0bccfc23402aba5bef6aedfa2f7f09579da2f586a2dcf6d4aa294475a469b848 | 89 | unchanged from Stage 1 | unchanged |
| docs/contracts/fixtures/_README.md | 0b9aa862268b4c4db87f5ee74dc55b6dfad082d04c463fca1dc10500e65bc994 | 72 | upgraded fixtures to authoritative | modified |
| docs/contracts/fixtures/approval_request.json | fce05104991ac56939388d3ce04eb9a3bffc989088d83fc533efd843060a5a9a | 37 | promoted from packages/.../tests/fixtures/approval_request.json | modified |
| docs/contracts/fixtures/digestion_item.json | 47ee0ab8dab7012f7c60796ab4b32b53b2284b9a22fa0903b5b627a41cc3e809 | 20 | promoted from packages/.../tests/fixtures/digestion_item.json | modified |
| docs/contracts/fixtures/run_record.json | 06b57494e7d4e39b47ec8b2b253f6a9575b013895c1b0b4fad7b7333748293ee | 37 | promoted from packages/.../tests/fixtures/run_record.json | modified |
| docs/contracts/fixtures/side_note.json | 4e443f30137ec78c8fa25ac65d56cf8be72d5ef1b95ac82f4f5bebef004c3a35 | 33 | promoted from packages/.../tests/fixtures/side_note.json | modified |
| docs/contracts/fixtures/source_record.json | 8d5a3eac521282079df9948e9ca4acd20783ec4c23d0ea0d63939eab3baf7aa4 | 38 | promoted from packages/.../tests/fixtures/source_record.json | modified |
| docs/contracts/fixtures/task.json | 9812f15801fd6640dd53c0604dd217f64b7922b4bcfb32dd587b0bb868c71723 | 31 | promoted from packages/.../tests/fixtures/task.json | modified |
| docs/contracts/phase1_1_api_contract.md | 192a391e972d6b731e3046a688d6be9af9c17ca0623cad14273c3215a082b9ae | 2950 | frontmatter 1.0.0 + §20 field constraint table | modified |
| docs/contracts/phase1_1_openapi.yaml | 5659e9e596b8a247f457937d247c89688daf27c79cc04bc65c32ca05e2589f30 | 1301 | OpenAPI 1.0.0 + components.schemas upgraded + HealthResponse example aligned (1.0.0/true) | modified |
| docs/contracts/phase1_1_pydantic_schemas.py | d6ab563ee36b220d2dde4dafa8035179b2c5a867cdfaf8a66addd3cdc23d818c | 955 | reverse-synced stub + CONTRACT_NOTE | modified |
| docs/decisions/D-Step4-1.md | a47c581be1c4e60775370a0ce2d4fe3fa888154e64dcd75387154c7012736154 | 356 | unchanged from Stage 1 | unchanged |
| docs/decisions/D-Step4-2.md | 446ef2f8e3f0fc7c50350370e1a068aea845e1b659e56464e1123ee33519d003 | 323 | unchanged from Stage 1 | unchanged |
| docs/decisions/D-Step4-3.md | b035f5a3de96ff71cc75a0ddc5f1f6770025e58118f7d2f24d908b6ea7484df1 | 322 | unchanged from Stage 1 | unchanged |
| docs/decisions/D-Step4-4A.md | dd61ad7e412ecff7adb433083fd97ab3fadd5e4cad5e49b6a3d19eed63c62296 | 309 | unchanged from Stage 1 | unchanged |
| docs/decisions/D-Step4-4B.md | bc2b9bf2063c846c5a1d3c2df5f87bf5d4edf15ad0c63a0cdeebeed00a322478 | 300 | unchanged from Stage 1 | unchanged |
| docs/decisions/D-Step4-4C.md | ec543a981d758aaef7400b198a99416a5169df52f7fed06107293a8483f87322 | 339 | unchanged from Stage 1 | unchanged |
| docs/decisions/D-Step4-4D.md | 8bbd7df434af15b524e4d52dda960d091f0df466c5610460746e7e4a9811d33b | 309 | unchanged from Stage 1 | unchanged |
| docs/domain_strategy.md | ce4487ff7db263f6bffa757ec2a279b98fc849f9c3fa9bacef54791adeb7aa1c | 89 | unchanged from Stage 1 | unchanged |
| docs/open_private_boundary.md | 7c9cc579381339068c5585eed09ef24ae2b90a860725cf63e4a97b4cd92ce106 | 103 | unchanged from Stage 1 | unchanged |
| docs/remote_gpt_handoff_protocol.md | e8e561f2e42fd0641a3d7712354ae9ec89d1a0b43a668ff9a490038dca7faaa9 | 271 | unchanged from Stage 1 | unchanged |
| docs/reviews/phase1.1/stage1_claude.md | be582bd5b5a0e3bda9217a84908a56a19b2514ad29415d1f58c5b9d9b7abd61d | 512 | added: Stage 1 Claude review summary | added |
| docs/reviews/phase1.1/stage1_codex.md | 7eebe4a09be45d62904971c89e9a1f72f5c4f961a408842187a7bcd01034ddb8 | 305 | added: Stage 1 Codex review summary | added |
| docs/reviews/phase1.1/freeze_claude.md | f3724060f5fbc8a5edf91e038d886ac75d00c5aaf29b1f28a0a860bb2c82002c | 380 | added (local PR): Stage 1.5 Freeze Claude review summary | added |
| docs/reviews/phase1.1/freeze_codex.md | 89c52652ab79f01fc2950b9ef13fa5056338dd25cf25e524ba6ca404aa224fb6 | 410 | added (local PR): Stage 1.5 Freeze Codex review summary | added |
| docs/tasks/TASK-1.1.4_schema.md | e15d102157e06c561ea29dfb9940f066b2a27be88f915f864356c83990be61d5 | 699 | unchanged from Stage 1 | unchanged |
| docs/tasks/TASK-1.1.5_ledger_placeholder.md | ef02b5af239dd9a683b032bdb7524293a0a31a57c61a05400af338533dae46a7 | 111 | unchanged from Stage 1 | unchanged |
| docs/tasks/TASK-1.1.6_guard_placeholder.md | cd19d2e066427f133efad8ee4f968ad0a8b87a56665787bcf67f9a4e3d54e32f | 111 | unchanged from Stage 1 | unchanged |
| docs/tasks/TASK-1.1.7_console_placeholder.md | fcc97b65ca45342c72655890ddd5fefd287a343d56a18faee174ac7fcef51104 | 111 | unchanged from Stage 1 | unchanged |
| legacy/README.md | a93620273b9e45d11f9befe41117230173f80d8c5c60da7aef0c3b6c1859b256 | 47 | unchanged from Stage 1 | unchanged |
| legacy/helixmind_phase1/.legacy_readonly_marker | 9910bc89df8f116f8a7bd6ad24f53a4922a2ca5dd8a681cc6b83d6c88786d430 | 12 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-console/README.md | 38b875ac9adc1194fa1c3036208c9fb405a572aaa3dbc603fb550d6d543c0457 | 41 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-console/package.json | a6056ec31b38a55c9b941964c2fb288e6d19e690dcf6759c9f404b83da6199b5 | 57 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-console/src/README.md | b3db44389a557cbdaf050444b8cdcc8bb5867cfb167e1295b97617404597c272 | 29 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/README.md | b0e16e0a8ca9d469fb61d164ea1a7a40b2b7839c938f13499f0c23a8f0bb004e | 44 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/pyproject.toml | 45a825e52a6a5bc501ff35e0918f94da5ba5e99fd812143ededfb187352405fb | 50 | local-fix: PEP 440 compliance (`0.1.0-stage0` -> `0.1.0+stage0`); enables CI `pip install -e` | modified |
| packages/noeticbraid-core/src/noeticbraid_core/__init__.py | 4e1960eca42fbf23eb2f900200bf6f3f5d4b8250a444a447b80060494f2222cb | 30 | __version__ upgraded to 1.0.0 | modified |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/__init__.py | f8ec06403f7c42e2ae7b5d38f42cf559d240e2defec7981b64e5908ab01d0c5a | 45 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/_common.py | b77a234dc9a1120d225c05791216d460ac3dfdc22968352f695210ecf3147ce3 | 247 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/approval_request.py | 25f69d6c89ed62e20cf82b9d29e51086e1b3dc497b4e314895c59782c8dc2c80 | 260 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/digestion_item.py | b4588a650d1de81b2db77cfa2f45d4f320b596dac578f805fe6e4d8c5e706629 | 256 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/run_record.py | 309daab5946a4078f4b9dae735554f833d0abc8207274ea25817a1a60fd433ff | 339 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/side_note.py | 54fefd99d01056161b0a44c1843f946c334cad267cef3ab8080150852730ba52 | 252 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/source_record.py | d314c1a51e7621efdc925d29a4c088e3aa524e5c49c7ab5b4489ea0e87d52bec | 375 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/task.py | 13be74b3444a11a08df74e2b37ef0519e4184ad0cc48921aa9a169d6add8b18a | 298 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/__init__.py | aecd3b825efba94d31b8f0361ec10f8a9792f08353d09a37ae502260f9f81587 | 7 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/conftest.py | 2a7fbad72f69224c9fa1fbcefd68eac9920cfb913d3b128fa366550f592cf7d8 | 86 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/fixtures/approval_request.json | 753169a713285590a9f9cf367bea6b5b9b72399e3ec2e1a350c85946995bacbf | 37 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/fixtures/digestion_item.json | e8ee12a60acacc2be08fe6db4e7e1d6899e32829f4347b8ab7fd3ba01a40eb41 | 20 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/fixtures/run_record.json | bfdcd8c774478639dea76533177a6d4f373f0d233dc4922440d7b26aa9e29283 | 37 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/fixtures/side_note.json | 90e31db6d65aefebdb37fad53439fe9664bbc4e014c7608852ffa68c40fd4332 | 33 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/fixtures/source_record.json | 974e4b599498f23a8793d94ff6f6a41374a0ca8187e03e8d3e0ad1c4bb5dc58d | 38 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/fixtures/task.json | 914bcffa8c4866d3c07ce98e7bc11f799f8c0c089839f823b65132e6c25777b5 | 31 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/test_schema_contract.py | 8c05e7f26da458aa06e8711963371cb7891c9eea49ab6d3d2408903db7d7baa1 | 429 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-core/tests/test_schema_models.py | cda42680ee77c2b4157857e02ac85982333a8d2e5c5e752590cdad662b4752ef | 1130 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-obsidian/README.md | 690ab83159ce21f83467b779fc09b4b81bdf3910a0490a58bb29b6b2552899d2 | 44 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-obsidian/pyproject.toml | c9f815332beaecfe8f071e6dbc0d96fdf722b44fcb4e4524761ae79e12584b6d | 39 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-obsidian/src/noeticbraid_obsidian/__init__.py | ad829ff1a5fd08ce9c509b4e369890c9e887062015677d487c3e69129727f954 | 8 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-runtime/README.md | 18a9e3ec5a5d33b946f077ab8677c3a83ba861e5f577adb5815ba64ca577ecc2 | 46 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-runtime/pyproject.toml | e122ae2138cf6ab8735d0afd12d86259399913c871b6b796b3c3a8ee2b2da935 | 41 | unchanged from Stage 1 | unchanged |
| packages/noeticbraid-runtime/src/noeticbraid_runtime/__init__.py | 5cb2e80ca4d9b0a8f7ed4887f4863fa8993401c172261aec8b81c95a50ce4845 | 8 | unchanged from Stage 1 | unchanged |
| pnpm-workspace.yaml | 61b0a4296254b2135754f9a2768b753fe8fa4d0327a22486455414e60d7612d5 | 3 | unchanged from Stage 1 | unchanged |
| private/README.md | 0577e688d8a02a35e52316b71ed41f623235e456052fdb2fc36347de4289e00e | 33 | unchanged from Stage 1 | unchanged |
| private/noeticbraid-browser-profiles/README.md | 57a8369124cc2583d896800d14ab9cde18935bbb497dae8e3578246302c1726e | 29 | unchanged from Stage 1 | unchanged |
| private/noeticbraid-private/README.md | 10d842462098ae3c596066d72025c5d3463926459c9406fe6d00599b09c0e25f | 30 | unchanged from Stage 1 | unchanged |
| private/noeticbraid-workflows-private/README.md | 9faeab2550af5cea4598d0cda33094f1a2a76033aebb846aa68dab95a445a260 | 34 | unchanged from Stage 1 | unchanged |
| pyproject.toml | 925f13146888b4a5971c7c6caec244a75408414838a01721a78c231698832f51 | 45 | unchanged from Stage 1 | unchanged |
| reuse_log/README.md | d0fa27c70d79b4d20e2b20c203d211ca6597c28153a63358b96b42838ac6d58c | 56 | unchanged from Stage 1 | unchanged |
| reuse_log/phase1_1_reuse_candidates.md | a4952b5c273a5f9d52a0c3e6f7847a590b94fee064d07a4841e22dd1a506c2fb | 592 | unchanged from Stage 1 | unchanged |
| scripts/README.md | 6d5577c98927fda65991291b4d4caefd7410b5b20c75d89bced9bae3ee2c65b7 | 40 | unchanged from Stage 1 | unchanged |
| scripts/apply_legacy_readonly.ps1 | 33259c4d5e7d3704a6bd7e5966005433165cfecdc93ce7bd3011ed4152b5c768 | 63 | unchanged from Stage 1 | unchanged |
| scripts/check_gate_1_0_to_1_1.ps1 | 866b3d01a283ee6673b6a9e06227b5aafd2dde231ca9e7f91fe69bb462433868 | 11 | unchanged from Stage 1 | unchanged |
| scripts/check_gate_1_0_to_1_1.py | 7742fecd278d7f7fb647ed1e38303c0f3107b52217cb31b8ce2dad7759c31dcd | 91 | unchanged from Stage 1 | unchanged |
| scripts/check_gate_1_1_to_1_2.ps1 | ec0376e4af264c8789dba2396173907eb50e289d49dd9f95c9a892417e3de407 | 11 | unchanged from Stage 1 | unchanged |
| scripts/check_gate_1_1_to_1_2.py | 2c39c0b0552bd451cd299988a0f3c8a5f9ba21b8992c4686e18a5342ec379d99 | 86 | unchanged from Stage 1 | unchanged |
| scripts/check_source_of_truth_consistency.py | 5391ffc76c28c845c8d23e2192c348d19652fa2ca69288e3c48d39fd26cc1278 | 308 | added: source-of-truth gate script | added |
| scripts/contract_diff.py | 98a2879119b11a2d7f623ef72f1c92971b5568052db3f0d77ff9b68771cb7692 | 504 | added: contract gate script | added |
| tests/README.md | 83c454c358d2ba7e7c53a2017b759e312bf84c501cfe19ad201de19d50d5d2cf | 28 | unchanged from Stage 1 | unchanged |
| tests/conftest.py | c2153691fb1ea87e2afb1725f8850ae8dc52a1afcaf102efea3a93964d6cafd6 | 17 | unchanged from Stage 1 | unchanged |
| tests/test_schema_smoke.py | 85b66c3b4b53b22ef03a01c22ea6205af558c5527a93b6de11493c332ad427ea | 79 | unchanged from Stage 1 | unchanged |

## Stage 1 → Stage 1.5 Diff Summary

修改 (modified, 13 files; 12 by GPT-A + 1 by local PR patch):
- docs/contracts/phase1_1_pydantic_schemas.py (reverse-synced stub + CONTRACT_NOTE) [GPT-A]
- docs/contracts/phase1_1_api_contract.md (frontmatter 1.0.0 + §20 constraint table) [GPT-A]
- docs/contracts/phase1_1_openapi.yaml (info.version 1.0.0 + components.schemas upgraded + HealthResponse example aligned to 1.0.0/true) [GPT-A + local M-fix]
- docs/contracts/fixtures/task.json (promoted from tests/fixtures/, meta fields upgraded) [GPT-A]
- docs/contracts/fixtures/run_record.json (promoted) [GPT-A]
- docs/contracts/fixtures/source_record.json (promoted) [GPT-A]
- docs/contracts/fixtures/approval_request.json (promoted) [GPT-A]
- docs/contracts/fixtures/side_note.json (promoted) [GPT-A]
- docs/contracts/fixtures/digestion_item.json (promoted) [GPT-A]
- docs/contracts/fixtures/_README.md (upgraded to authoritative) [GPT-A]
- packages/noeticbraid-core/src/noeticbraid_core/__init__.py (__version__ "0.1.0-stage1-candidate" -> "1.0.0") [GPT-A]
- manifest.md (this file; rewritten by GPT-A, then local-edited to record local patches) [GPT-A + local]
- packages/noeticbraid-core/pyproject.toml (PEP 440: "0.1.0-stage0" -> "0.1.0+stage0"; unblocks CI `pip install -e`) [local PR patch — Codex S fix]

总计 = 3 contract docs + 6 fixtures JSON + 1 fixtures _README + 1 __init__.py + 1 manifest + 1 pyproject.toml = **13 modified files**.

新增 (added, 8 files; 6 by GPT-A + 2 by local PR patch):
- scripts/contract_diff.py [GPT-A]
- scripts/check_source_of_truth_consistency.py [GPT-A]
- .github/workflows/ci.yml [GPT-A]
- docs/audit_trail.md [GPT-A]
- docs/reviews/phase1.1/stage1_claude.md [GPT-A]
- docs/reviews/phase1.1/stage1_codex.md [GPT-A]
- docs/reviews/phase1.1/freeze_claude.md [local PR — Stage 1.5 review summary]
- docs/reviews/phase1.1/freeze_codex.md [local PR — Stage 1.5 review summary]

未动 (unchanged from main b8d7152, 71 files):
- 全部 packages/noeticbraid-core/src/noeticbraid_core/schemas/** (8 files: __init__/_common + 6 models)
- 全部 packages/noeticbraid-core/tests/** (含 fixtures/ 6 个 .json 源文件 + 4 个 .py)
- tests/test_schema_smoke.py
- 全部 docs/decisions/** / docs/architecture/** / docs/tasks/** / docs/*.md (顶级文档)
- 全部 reuse_log/** / legacy/** / private/**
- 全部 packages/noeticbraid-{console,obsidian,runtime}/**
- 顶级 README.md / LICENSE / NOTICE / pyproject.toml / pnpm-workspace.yaml / .gitignore / .editorconfig
- docs/contracts/contract_change_requests/** (2 files)

## SHA256 audit (Stage 1 baseline equivalence)

下列文件 SHA256 与 Stage 1 manifest 完全一致:

- packages/noeticbraid-core/src/noeticbraid_core/schemas/__init__.py: f8ec06403f7c42e2ae7b5d38f42cf559d240e2defec7981b64e5908ab01d0c5a ✅
- packages/noeticbraid-core/src/noeticbraid_core/schemas/_common.py: b77a234dc9a1120d225c05791216d460ac3dfdc22968352f695210ecf3147ce3 ✅
- packages/noeticbraid-core/src/noeticbraid_core/schemas/task.py: 13be74b3444a11a08df74e2b37ef0519e4184ad0cc48921aa9a169d6add8b18a ✅
- packages/noeticbraid-core/src/noeticbraid_core/schemas/run_record.py: 309daab5946a4078f4b9dae735554f833d0abc8207274ea25817a1a60fd433ff ✅
- packages/noeticbraid-core/src/noeticbraid_core/schemas/source_record.py: d314c1a51e7621efdc925d29a4c088e3aa524e5c49c7ab5b4489ea0e87d52bec ✅
- packages/noeticbraid-core/src/noeticbraid_core/schemas/approval_request.py: 25f69d6c89ed62e20cf82b9d29e51086e1b3dc497b4e314895c59782c8dc2c80 ✅
- packages/noeticbraid-core/src/noeticbraid_core/schemas/side_note.py: 54fefd99d01056161b0a44c1843f946c334cad267cef3ab8080150852730ba52 ✅
- packages/noeticbraid-core/src/noeticbraid_core/schemas/digestion_item.py: b4588a650d1de81b2db77cfa2f45d4f320b596dac578f805fe6e4d8c5e706629 ✅
- packages/noeticbraid-core/tests/__init__.py: aecd3b825efba94d31b8f0361ec10f8a9792f08353d09a37ae502260f9f81587 ✅
- packages/noeticbraid-core/tests/conftest.py: 2a7fbad72f69224c9fa1fbcefd68eac9920cfb913d3b128fa366550f592cf7d8 ✅
- packages/noeticbraid-core/tests/test_schema_models.py: cda42680ee77c2b4157857e02ac85982333a8d2e5c5e752590cdad662b4752ef ✅
- packages/noeticbraid-core/tests/test_schema_contract.py: 8c05e7f26da458aa06e8711963371cb7891c9eea49ab6d3d2408903db7d7baa1 ✅
- packages/noeticbraid-core/tests/fixtures/task.json: 914bcffa8c4866d3c07ce98e7bc11f799f8c0c089839f823b65132e6c25777b5 ✅
- packages/noeticbraid-core/tests/fixtures/run_record.json: bfdcd8c774478639dea76533177a6d4f373f0d233dc4922440d7b26aa9e29283 ✅
- packages/noeticbraid-core/tests/fixtures/source_record.json: 974e4b599498f23a8793d94ff6f6a41374a0ca8187e03e8d3e0ad1c4bb5dc58d ✅
- packages/noeticbraid-core/tests/fixtures/approval_request.json: 753169a713285590a9f9cf367bea6b5b9b72399e3ec2e1a350c85946995bacbf ✅
- packages/noeticbraid-core/tests/fixtures/side_note.json: 90e31db6d65aefebdb37fad53439fe9664bbc4e014c7608852ffa68c40fd4332 ✅
- packages/noeticbraid-core/tests/fixtures/digestion_item.json: e8ee12a60acacc2be08fe6db4e7e1d6899e32829f4347b8ab7fd3ba01a40eb41 ✅
- packages/noeticbraid-core/pyproject.toml: 3e7cd30232fe944a4aeea60a18b9ba501e0f94ae371d9ca43757e555ae8d2f07 (Stage 1 baseline) -> 45a825e52a6a5bc501ff35e0918f94da5ba5e99fd812143ededfb187352405fb (after local PEP 440 fix) — 仅本地补丁 commit，非 GPT-A 输出
- tests/test_schema_smoke.py: 85b66c3b4b53b22ef03a01c22ea6205af558c5527a93b6de11493c332ad427ea ✅

Other protected Stage 1 paths also remain byte-identical to the Stage 1 manifest:
- `reuse_log/**`: ✅ all Stage 1 hashes match
- `legacy/**`: ✅ all Stage 1 hashes match
- `private/**`: ✅ all Stage 1 hashes match
- `docs/decisions/**`: ✅ all Stage 1 hashes match
- `docs/architecture/**`: ✅ all Stage 1 hashes match
- `docs/tasks/**`: ✅ all Stage 1 hashes match
- `docs/*.md` top-level: ✅ all Stage 1 hashes match
- `docs/contracts/contract_change_requests/**`: ✅ all Stage 1 hashes match
- `packages/noeticbraid-console/**`: ✅ all Stage 1 hashes match
- `packages/noeticbraid-obsidian/**`: ✅ all Stage 1 hashes match
- `packages/noeticbraid-runtime/**`: ✅ all Stage 1 hashes match
- top-level frozen files: ✅ all Stage 1 hashes match

## contract_diff self-verification (run before delivery)

```text
[PASS] Task: field set + bare types + Literal values equivalent
[PASS] RunRecord: field set + bare types + Literal values equivalent
[PASS] SourceRecord: field set + bare types + Literal values equivalent
[PASS] ApprovalRequest: field set + bare types + Literal values equivalent
[PASS] SideNote: field set + bare types + Literal values equivalent
[PASS] DigestionItem: field set + bare types + Literal values equivalent

contract_diff: PASS (6 models equivalent)
```

## source-of-truth self-verification (run before delivery)

```text
source_of_truth_check: PASS (no Source-of-truth markers in repo; future-ready)
```

## 14-item self-check

- [PASS] 1. schemas/ byte-identical to Stage 1
- [PASS] 2. tests/ byte-identical to Stage 1
- [PASS] 3. contract_diff PASS (6 models equivalent)
- [PASS] 4. api_contract §20 covers all Stage 1 Field constraints (incl. M-1/L-1/L-2)
- [PASS] 5. OpenAPI 1.0.0 + components.schemas complete
- [PASS] 6. fixtures 6 files promoted; meta upgraded
- [PASS] 7. manifest 1.0.0 / frozen / authoritative
- [PASS] 8. __init__.py __version__ = "1.0.0"
- [PASS] 9. CI workflow triggers + steps complete
- [PASS] 10. audit_trail 2 rows (Stage 1 PASS / Freeze TBD)
- [PASS] 11. reviews summaries in repo (claude + codex)
- [PASS] 12. contract_diff.py self-test PASS
- [PASS] 13. check_source_of_truth_consistency.py self-test PASS
- [PASS] 14. blacklist untouched + zip naming
