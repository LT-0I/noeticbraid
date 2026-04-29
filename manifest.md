# Stage 1 Manifest

- contract_version: 0.1.0 (still draft, candidate_for: 1.0.0)
- candidate_for: 1.0.0
- status: pending_local_freeze
- authoritative: false
- generated_at: 2026-04-28T12:02:01Z
- total_files_including_manifest: 84
- total_files_excluding_manifest: 83
- zip_sha256: see external `noeticbraid_phase1_1_stage1.zip.sha256`
- stage0_input_files_carried_excluding_manifest: 64 (all present; 62 unchanged + 2 allowed Stage 1 modifications)
- stage1_added_files: 19
- stage1_modified_files: 2 (packages/noeticbraid-core/pyproject.toml + src/noeticbraid_core/__init__.py)

## Self-reference note

`manifest.md` is regenerated for Stage 1 and excluded from its own SHA table because that would make the hash self-referential. All other files are listed with exact SHA256 values.

## Source-of-truth note (consumed by local main session)

- `packages/noeticbraid-core/src/noeticbraid_core/schemas/**.py` = 1.0.0 candidate full implementation (Field/validator/Config/business methods).
- `docs/contracts/**` = unchanged Stage 0 baseline (all 12 files SHA256 == Stage 0 manifest).
- Local main session will, at freeze commit:
  - reverse-sync schemas -> `docs/contracts/phase1_1_pydantic_schemas.py` (stub form)
  - sync constraints -> `docs/contracts/phase1_1_api_contract.md` field constraint table
  - sync `phase1_1_openapi.yaml` components.schemas
  - promote `packages/noeticbraid-core/tests/fixtures/*.json` -> `docs/contracts/fixtures/*.json`
  - upgrade contract_version 0.1.0 -> 1.0.0
  - run `scripts/contract_diff.py` (created by local main session before freeze) to verify field set + bare type + Literal equivalence

## File List

| 路径 | SHA256 | 字数 | 用途 |
|---|---|---:|---|
| .editorconfig | 48bf56a6cd915c2528f22f05c6a709d296abaaef8664ec4bd641f134f4561f81 | 27 | unchanged from Stage 0: stage0 artifact |
| .gitignore | a445465e8de18782fde3bf9245451bddc3faab7eb99eaa0593cfd75043a925cc | 47 | unchanged from Stage 0: stage0 artifact |
| LICENSE | 2dcba93cf6b0df20e714d4b20df5daaacbde7843353435c1f3538f68a4a0df78 | 1413 | unchanged from Stage 0: Apache-2.0 license text |
| NOTICE | 1ec900193816f3206f0359a095e8d9e129eafc1b607e3f58852aa5caf54f18ae | 50 | unchanged from Stage 0: third-party notice placeholder |
| README.md | e5b85971da2a5711ca73d216ca791a2030c11b5c4da66bc74f86a5b871cb2cc8 | 232 | unchanged from Stage 0: project root explanation |
| docs/architecture/step3_authority.md | 4e4c39752baa88d1102527ba8373febede0b3b72859661cb5cb8ea3a03ecb807 | 115 | unchanged from Stage 0: architecture authority/design note |
| docs/architecture/step4_authority.md | e4bc524754075fb95c1e024300e84a47cb5c996329ff66652f2c8d6fa3e98510 | 85 | unchanged from Stage 0: architecture authority/design note |
| docs/architecture/step5_phase1_1_design.md | 138e523322289a11a2789b3323514add9315b53f2a3f2911daf1a32e5744ba38 | 2010 | unchanged from Stage 0: architecture authority/design note |
| docs/contracts/contract_change_requests/README.md | 2d40e068010b07349baed62bbac678a96a9cafd9ef59a15e8ff01afac6e8e8ed | 85 | unchanged from Stage 0: draft contract artifact |
| docs/contracts/contract_change_requests/_template.md | 0bccfc23402aba5bef6aedfa2f7f09579da2f586a2dcf6d4aa294475a469b848 | 89 | unchanged from Stage 0: draft contract artifact |
| docs/contracts/fixtures/_README.md | 254ab994e3d7486517613e243924e2408a80eb1549c477bae5fbe5309a0198f9 | 62 | unchanged from Stage 0: draft non-binding fixture/example |
| docs/contracts/fixtures/approval_request.json | c5f6452d6875d91dc94c9b0a5db460ba895ea24f1a3394311edc4b7fa0aff5ee | 16 | unchanged from Stage 0: draft non-binding fixture/example |
| docs/contracts/fixtures/digestion_item.json | e893347bea09ed52da34e0a9b28439b00ead5c8fd69df476fad02ca0e67cfdde | 14 | unchanged from Stage 0: draft non-binding fixture/example |
| docs/contracts/fixtures/run_record.json | f14fdc44b3a31716ea6427eebf8637295e36cdb1ab3446ffbba4c4530fbbd4ad | 18 | unchanged from Stage 0: draft non-binding fixture/example |
| docs/contracts/fixtures/side_note.json | 6deff6b8c0377955cf656c56ed856199bcd2f02b138e5befc8424c34ebcbce60 | 17 | unchanged from Stage 0: draft non-binding fixture/example |
| docs/contracts/fixtures/source_record.json | 2416d35baac3c3a8e968ad918bdfb9baa04ef699724a7f756a216fdbf1c6d686 | 19 | unchanged from Stage 0: draft non-binding fixture/example |
| docs/contracts/fixtures/task.json | 55fb483606fc368623aead6cecda406d4163eaf433f93e21b7d39f67a854a5f8 | 18 | unchanged from Stage 0: draft non-binding fixture/example |
| docs/contracts/phase1_1_api_contract.md | 211b5d063efeda885eb7cdfff4e3c34546db412fefd50efa6e96c5a6897fa6ec | 1549 | unchanged from Stage 0: draft contract artifact |
| docs/contracts/phase1_1_openapi.yaml | 9c9e194c0ddc14c1c4c62e424aa0a4ccf3ecf4616516478b24b036a23e2c2d2e | 230 | unchanged from Stage 0: draft contract artifact |
| docs/contracts/phase1_1_pydantic_schemas.py | 5abe8cb7ba53a6e45d49d8a8778eed18d67120402d7bf9f3ffeb944cdf57462e | 250 | unchanged from Stage 0: draft contract artifact |
| docs/decisions/D-Step4-1.md | a47c581be1c4e60775370a0ce2d4fe3fa888154e64dcd75387154c7012736154 | 356 | unchanged from Stage 0: user decision record |
| docs/decisions/D-Step4-2.md | 446ef2f8e3f0fc7c50350370e1a068aea845e1b659e56464e1123ee33519d003 | 323 | unchanged from Stage 0: user decision record |
| docs/decisions/D-Step4-3.md | b035f5a3de96ff71cc75a0ddc5f1f6770025e58118f7d2f24d908b6ea7484df1 | 322 | unchanged from Stage 0: user decision record |
| docs/decisions/D-Step4-4A.md | dd61ad7e412ecff7adb433083fd97ab3fadd5e4cad5e49b6a3d19eed63c62296 | 309 | unchanged from Stage 0: user decision record |
| docs/decisions/D-Step4-4B.md | bc2b9bf2063c846c5a1d3c2df5f87bf5d4edf15ad0c63a0cdeebeed00a322478 | 300 | unchanged from Stage 0: user decision record |
| docs/decisions/D-Step4-4C.md | ec543a981d758aaef7400b198a99416a5169df52f7fed06107293a8483f87322 | 339 | unchanged from Stage 0: user decision record |
| docs/decisions/D-Step4-4D.md | 8bbd7df434af15b524e4d52dda960d091f0df466c5610460746e7e4a9811d33b | 309 | unchanged from Stage 0: user decision record |
| docs/domain_strategy.md | ce4487ff7db263f6bffa757ec2a279b98fc849f9c3fa9bacef54791adeb7aa1c | 89 | unchanged from Stage 0: project documentation |
| docs/open_private_boundary.md | 7c9cc579381339068c5585eed09ef24ae2b90a860725cf63e4a97b4cd92ce106 | 103 | unchanged from Stage 0: project documentation |
| docs/remote_gpt_handoff_protocol.md | e8e561f2e42fd0641a3d7712354ae9ec89d1a0b43a668ff9a490038dca7faaa9 | 271 | unchanged from Stage 0: project documentation |
| docs/tasks/TASK-1.1.4_schema.md | e15d102157e06c561ea29dfb9940f066b2a27be88f915f864356c83990be61d5 | 699 | unchanged from Stage 0: task card or placeholder |
| docs/tasks/TASK-1.1.5_ledger_placeholder.md | ef02b5af239dd9a683b032bdb7524293a0a31a57c61a05400af338533dae46a7 | 111 | unchanged from Stage 0: task card or placeholder |
| docs/tasks/TASK-1.1.6_guard_placeholder.md | cd19d2e066427f133efad8ee4f968ad0a8b87a56665787bcf67f9a4e3d54e32f | 111 | unchanged from Stage 0: task card or placeholder |
| docs/tasks/TASK-1.1.7_console_placeholder.md | fcc97b65ca45342c72655890ddd5fefd287a343d56a18faee174ac7fcef51104 | 111 | unchanged from Stage 0: task card or placeholder |
| legacy/README.md | a93620273b9e45d11f9befe41117230173f80d8c5c60da7aef0c3b6c1859b256 | 47 | unchanged from Stage 0: legacy read-only marker/docs |
| legacy/helixmind_phase1/.legacy_readonly_marker | 9910bc89df8f116f8a7bd6ad24f53a4922a2ca5dd8a681cc6b83d6c88786d430 | 12 | unchanged from Stage 0: legacy read-only marker/docs |
| packages/noeticbraid-console/README.md | 38b875ac9adc1194fa1c3036208c9fb405a572aaa3dbc603fb550d6d543c0457 | 41 | unchanged from Stage 0: package skeleton placeholder |
| packages/noeticbraid-console/package.json | a6056ec31b38a55c9b941964c2fb288e6d19e690dcf6759c9f404b83da6199b5 | 57 | unchanged from Stage 0: workspace/package metadata |
| packages/noeticbraid-console/src/README.md | b3db44389a557cbdaf050444b8cdcc8bb5867cfb167e1295b97617404597c272 | 29 | unchanged from Stage 0: package skeleton placeholder |
| packages/noeticbraid-core/README.md | b0e16e0a8ca9d469fb61d164ea1a7a40b2b7839c938f13499f0c23a8f0bb004e | 44 | unchanged from Stage 0: package skeleton placeholder |
| packages/noeticbraid-core/pyproject.toml | 3e7cd30232fe944a4aeea60a18b9ba501e0f94ae371d9ca43757e555ae8d2f07 | 50 | modified: add pydantic runtime dependency and pytest test extra |
| packages/noeticbraid-core/src/noeticbraid_core/__init__.py | 89ec44c37add1e65dfa3a35a58f2f9b6bdfbf7b249157da27f63f96ea320c4d9 | 33 | modified: export six schema models from noeticbraid_core |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/__init__.py | f8ec06403f7c42e2ae7b5d38f42cf559d240e2defec7981b64e5908ab01d0c5a | 45 | added: export 6 Stage 1 candidate models |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/_common.py | b77a234dc9a1120d225c05791216d460ac3dfdc22968352f695210ecf3147ce3 | 247 | added: shared schema validators/helpers |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/approval_request.py | 25f69d6c89ed62e20cf82b9d29e51086e1b3dc497b4e314895c59782c8dc2c80 | 260 | added: ApprovalRequest full implementation |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/digestion_item.py | b4588a650d1de81b2db77cfa2f45d4f320b596dac578f805fe6e4d8c5e706629 | 256 | added: DigestionItem full implementation |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/run_record.py | 309daab5946a4078f4b9dae735554f833d0abc8207274ea25817a1a60fd433ff | 339 | added: RunRecord full implementation |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/side_note.py | 54fefd99d01056161b0a44c1843f946c334cad267cef3ab8080150852730ba52 | 252 | added: SideNote full implementation |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/source_record.py | d314c1a51e7621efdc925d29a4c088e3aa524e5c49c7ab5b4489ea0e87d52bec | 375 | added: SourceRecord full implementation |
| packages/noeticbraid-core/src/noeticbraid_core/schemas/task.py | 13be74b3444a11a08df74e2b37ef0519e4184ad0cc48921aa9a169d6add8b18a | 298 | added: Task full implementation |
| packages/noeticbraid-core/tests/__init__.py | aecd3b825efba94d31b8f0361ec10f8a9792f08353d09a37ae502260f9f81587 | 7 | added: package test marker |
| packages/noeticbraid-core/tests/conftest.py | 2a7fbad72f69224c9fa1fbcefd68eac9920cfb913d3b128fa366550f592cf7d8 | 86 | added: pytest fixture loader and src path helper |
| packages/noeticbraid-core/tests/fixtures/approval_request.json | 753169a713285590a9f9cf367bea6b5b9b72399e3ec2e1a350c85946995bacbf | 37 | added: ApprovalRequest candidate test fixture |
| packages/noeticbraid-core/tests/fixtures/digestion_item.json | e8ee12a60acacc2be08fe6db4e7e1d6899e32829f4347b8ab7fd3ba01a40eb41 | 20 | added: DigestionItem candidate test fixture |
| packages/noeticbraid-core/tests/fixtures/run_record.json | bfdcd8c774478639dea76533177a6d4f373f0d233dc4922440d7b26aa9e29283 | 37 | added: RunRecord candidate test fixture |
| packages/noeticbraid-core/tests/fixtures/side_note.json | 90e31db6d65aefebdb37fad53439fe9664bbc4e014c7608852ffa68c40fd4332 | 33 | added: SideNote candidate test fixture |
| packages/noeticbraid-core/tests/fixtures/source_record.json | 974e4b599498f23a8793d94ff6f6a41374a0ca8187e03e8d3e0ad1c4bb5dc58d | 38 | added: SourceRecord candidate test fixture |
| packages/noeticbraid-core/tests/fixtures/task.json | 914bcffa8c4866d3c07ce98e7bc11f799f8c0c089839f823b65132e6c25777b5 | 31 | added: Task candidate test fixture |
| packages/noeticbraid-core/tests/test_schema_contract.py | 8c05e7f26da458aa06e8711963371cb7891c9eea49ab6d3d2408903db7d7baa1 | 429 | added: field/Literal/bare type equivalence tests |
| packages/noeticbraid-core/tests/test_schema_models.py | cda42680ee77c2b4157857e02ac85982333a8d2e5c5e752590cdad662b4752ef | 1130 | added: validation, round-trip, fixture, and business method tests |
| packages/noeticbraid-obsidian/README.md | 690ab83159ce21f83467b779fc09b4b81bdf3910a0490a58bb29b6b2552899d2 | 44 | unchanged from Stage 0: package skeleton placeholder |
| packages/noeticbraid-obsidian/pyproject.toml | c9f815332beaecfe8f071e6dbc0d96fdf722b44fcb4e4524761ae79e12584b6d | 39 | unchanged from Stage 0: workspace/package metadata |
| packages/noeticbraid-obsidian/src/noeticbraid_obsidian/__init__.py | ad829ff1a5fd08ce9c509b4e369890c9e887062015677d487c3e69129727f954 | 8 | unchanged from Stage 0: package skeleton placeholder |
| packages/noeticbraid-runtime/README.md | 18a9e3ec5a5d33b946f077ab8677c3a83ba861e5f577adb5815ba64ca577ecc2 | 46 | unchanged from Stage 0: package skeleton placeholder |
| packages/noeticbraid-runtime/pyproject.toml | e122ae2138cf6ab8735d0afd12d86259399913c871b6b796b3c3a8ee2b2da935 | 41 | unchanged from Stage 0: workspace/package metadata |
| packages/noeticbraid-runtime/src/noeticbraid_runtime/__init__.py | 5cb2e80ca4d9b0a8f7ed4887f4863fa8993401c172261aec8b81c95a50ce4845 | 8 | unchanged from Stage 0: package skeleton placeholder |
| pnpm-workspace.yaml | 61b0a4296254b2135754f9a2768b753fe8fa4d0327a22486455414e60d7612d5 | 3 | unchanged from Stage 0: workspace/package metadata |
| private/README.md | 0577e688d8a02a35e52316b71ed41f623235e456052fdb2fc36347de4289e00e | 33 | unchanged from Stage 0: private directory placeholder |
| private/noeticbraid-browser-profiles/README.md | 57a8369124cc2583d896800d14ab9cde18935bbb497dae8e3578246302c1726e | 29 | unchanged from Stage 0: private directory placeholder |
| private/noeticbraid-private/README.md | 10d842462098ae3c596066d72025c5d3463926459c9406fe6d00599b09c0e25f | 30 | unchanged from Stage 0: private directory placeholder |
| private/noeticbraid-workflows-private/README.md | 9faeab2550af5cea4598d0cda33094f1a2a76033aebb846aa68dab95a445a260 | 34 | unchanged from Stage 0: private directory placeholder |
| pyproject.toml | 925f13146888b4a5971c7c6caec244a75408414838a01721a78c231698832f51 | 45 | unchanged from Stage 0: workspace/package metadata |
| reuse_log/README.md | d0fa27c70d79b4d20e2b20c203d211ca6597c28153a63358b96b42838ac6d58c | 56 | unchanged from Stage 0: reuse candidate log |
| reuse_log/phase1_1_reuse_candidates.md | a4952b5c273a5f9d52a0c3e6f7847a590b94fee064d07a4841e22dd1a506c2fb | 592 | unchanged from Stage 0: reuse candidate log |
| scripts/README.md | 6d5577c98927fda65991291b4d4caefd7410b5b20c75d89bced9bae3ee2c65b7 | 40 | unchanged from Stage 0: gate/helper script |
| scripts/apply_legacy_readonly.ps1 | 33259c4d5e7d3704a6bd7e5966005433165cfecdc93ce7bd3011ed4152b5c768 | 63 | unchanged from Stage 0: gate/helper script |
| scripts/check_gate_1_0_to_1_1.ps1 | 866b3d01a283ee6673b6a9e06227b5aafd2dde231ca9e7f91fe69bb462433868 | 11 | unchanged from Stage 0: gate/helper script |
| scripts/check_gate_1_0_to_1_1.py | 7742fecd278d7f7fb647ed1e38303c0f3107b52217cb31b8ce2dad7759c31dcd | 91 | unchanged from Stage 0: gate/helper script |
| scripts/check_gate_1_1_to_1_2.ps1 | ec0376e4af264c8789dba2396173907eb50e289d49dd9f95c9a892417e3de407 | 11 | unchanged from Stage 0: gate/helper script |
| scripts/check_gate_1_1_to_1_2.py | 2c39c0b0552bd451cd299988a0f3c8a5f9ba21b8992c4686e18a5342ec379d99 | 86 | unchanged from Stage 0: gate/helper script |
| tests/README.md | 83c454c358d2ba7e7c53a2017b759e312bf84c501cfe19ad201de19d50d5d2cf | 28 | unchanged from Stage 0: test directory placeholder |
| tests/conftest.py | c2153691fb1ea87e2afb1725f8850ae8dc52a1afcaf102efea3a93964d6cafd6 | 17 | unchanged from Stage 0: test directory placeholder |
| tests/test_schema_smoke.py | 85b66c3b4b53b22ef03a01c22ea6205af558c5527a93b6de11493c332ad427ea | 79 | added: top-level import and Task round-trip smoke test |

## Stage 0 -> Stage 1 Diff Summary

新增 (added, all under allowed Stage 1 paths):
- packages/noeticbraid-core/src/noeticbraid_core/schemas/__init__.py
- packages/noeticbraid-core/src/noeticbraid_core/schemas/_common.py
- packages/noeticbraid-core/src/noeticbraid_core/schemas/approval_request.py
- packages/noeticbraid-core/src/noeticbraid_core/schemas/digestion_item.py
- packages/noeticbraid-core/src/noeticbraid_core/schemas/run_record.py
- packages/noeticbraid-core/src/noeticbraid_core/schemas/side_note.py
- packages/noeticbraid-core/src/noeticbraid_core/schemas/source_record.py
- packages/noeticbraid-core/src/noeticbraid_core/schemas/task.py
- packages/noeticbraid-core/tests/__init__.py
- packages/noeticbraid-core/tests/conftest.py
- packages/noeticbraid-core/tests/fixtures/approval_request.json
- packages/noeticbraid-core/tests/fixtures/digestion_item.json
- packages/noeticbraid-core/tests/fixtures/run_record.json
- packages/noeticbraid-core/tests/fixtures/side_note.json
- packages/noeticbraid-core/tests/fixtures/source_record.json
- packages/noeticbraid-core/tests/fixtures/task.json
- packages/noeticbraid-core/tests/test_schema_contract.py
- packages/noeticbraid-core/tests/test_schema_models.py
- tests/test_schema_smoke.py

修改 (modified, exactly 2 files):
- packages/noeticbraid-core/pyproject.toml
- packages/noeticbraid-core/src/noeticbraid_core/__init__.py

未动 (unchanged from Stage 0, 62 non-manifest files):
- 所有 `docs/contracts/**` (12 files)
- 所有 `docs/decisions/**` (7 files)
- 所有 `docs/architecture/**` / `docs/tasks/**` / `docs/*.md` (顶级文档)
- 所有 `reuse_log/**`, `scripts/**`, `legacy/**`, `private/**`
- 所有 `packages/noeticbraid-{console,obsidian,runtime}/**`
- 顶级 `README.md` / `LICENSE` / `NOTICE` / `pyproject.toml` / `pnpm-workspace.yaml` / `.gitignore` / `.editorconfig`
- `tests/README.md` / `tests/conftest.py`

## SHA256 audit (Stage 0 baseline equivalence)

下面 12 文件 SHA256 与 Stage 0 manifest 一致:

- docs/contracts/phase1_1_pydantic_schemas.py: 5abe8cb7ba53a6e45d49d8a8778eed18d67120402d7bf9f3ffeb944cdf57462e ✅ matches Stage 0
- docs/contracts/phase1_1_api_contract.md: 211b5d063efeda885eb7cdfff4e3c34546db412fefd50efa6e96c5a6897fa6ec ✅ matches Stage 0
- docs/contracts/phase1_1_openapi.yaml: 9c9e194c0ddc14c1c4c62e424aa0a4ccf3ecf4616516478b24b036a23e2c2d2e ✅ matches Stage 0
- docs/contracts/fixtures/_README.md: 254ab994e3d7486517613e243924e2408a80eb1549c477bae5fbe5309a0198f9 ✅ matches Stage 0
- docs/contracts/fixtures/task.json: 55fb483606fc368623aead6cecda406d4163eaf433f93e21b7d39f67a854a5f8 ✅ matches Stage 0
- docs/contracts/fixtures/run_record.json: f14fdc44b3a31716ea6427eebf8637295e36cdb1ab3446ffbba4c4530fbbd4ad ✅ matches Stage 0
- docs/contracts/fixtures/source_record.json: 2416d35baac3c3a8e968ad918bdfb9baa04ef699724a7f756a216fdbf1c6d686 ✅ matches Stage 0
- docs/contracts/fixtures/approval_request.json: c5f6452d6875d91dc94c9b0a5db460ba895ea24f1a3394311edc4b7fa0aff5ee ✅ matches Stage 0
- docs/contracts/fixtures/side_note.json: 6deff6b8c0377955cf656c56ed856199bcd2f02b138e5befc8424c34ebcbce60 ✅ matches Stage 0
- docs/contracts/fixtures/digestion_item.json: e893347bea09ed52da34e0a9b28439b00ead5c8fd69df476fad02ca0e67cfdde ✅ matches Stage 0
- docs/contracts/contract_change_requests/README.md: 2d40e068010b07349baed62bbac678a96a9cafd9ef59a15e8ff01afac6e8e8ed ✅ matches Stage 0
- docs/contracts/contract_change_requests/_template.md: 0bccfc23402aba5bef6aedfa2f7f09579da2f586a2dcf6d4aa294475a469b848 ✅ matches Stage 0

Other frozen Stage 0 paths also match their Stage 0 manifest SHA256 values:
- `reuse_log/**`: ✅ all Stage 0 hashes match
- `legacy/**`: ✅ all Stage 0 hashes match
- `private/**`: ✅ all Stage 0 hashes match
- `scripts/**`: ✅ all Stage 0 hashes match
- `docs/decisions/**`: ✅ all Stage 0 hashes match
- `docs/architecture/**`: ✅ all Stage 0 hashes match
- `docs/tasks/**`: ✅ all Stage 0 hashes match
- `docs/*.md`: ✅ all Stage 0 hashes match
- `packages/noeticbraid-console/**`: ✅ all Stage 0 hashes match
- `packages/noeticbraid-obsidian/**`: ✅ all Stage 0 hashes match
- `packages/noeticbraid-runtime/**`: ✅ all Stage 0 hashes match
- top-level frozen files: ✅ all Stage 0 hashes match

## Schema equivalence self-audit

- Task: field set + bare types + Literal value sets match Stage 0 stub.
- RunRecord: field set + bare types + Literal value sets match Stage 0 stub.
- SourceRecord: field set + bare types + Literal value sets match Stage 0 stub.
- ApprovalRequest: field set + bare types + Literal value sets match Stage 0 stub.
- SideNote: field set + bare types + Literal value sets match Stage 0 stub.
- DigestionItem: field set + bare types + Literal value sets match Stage 0 stub.
- Constraints/defaults/validators/business methods are candidate implementation details and intentionally not part of stub equivalence comparison.

## Optional contract change request notes

- none

## Note on contract_diff.py

GPT-A did not implement, execute, or import `scripts/contract_diff.py` or `scripts/check_source_of_truth_consistency.py`. The local main session should consume `packages/noeticbraid-core/src/noeticbraid_core/schemas/` during the freeze flow and perform field set + bare type + Literal equivalence checks against the unchanged Stage 0 stub.
