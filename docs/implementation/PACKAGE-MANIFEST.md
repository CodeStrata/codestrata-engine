# Package revision manifest

**Package revision:** `ENGINE-2026-09-15-R1`

Recorded at package build time (this delivery), covering every document, hook, and prompt file in this package (this manifest file necessarily excludes itself). Per Kickoff Steps Phase 2, verify this manifest against the actual files on `release/engine-next` before G00 PASS — recompute the digests yourself rather than trusting this table blindly, and record the reviewer and result in the G00 ledger. For the two hook files, also confirm the executable bit survived copying/extraction (`ls -l engine-docs-implementation/git-hooks/`) — a zip transfer can lose it depending on the tool used to extract.

## Main specifications (engine-docs-implementation/)

| Relative path | SHA-256 |
|---|---|
| `engine-docs-implementation/CodeStrata-Engine-Cursor-Prompts.md` | `ecd16abcab0d884e1ce6628354247dd5e65926d2b95db6fe407c1dfde10ace39` |
| `engine-docs-implementation/CodeStrata-Engine-Kickoff-Steps.md` | `e4de2734eb5d322ed74bd977d18aad409827025c33d8fb88a453313f08749fec` |
| `engine-docs-implementation/CodeStrata-Engine-MVP-Backlog.md` | `f043d1fb6bd3bef1549a0de30d6ddbf4d3e6f7c2fd00f05fb038cbf773a15c74` |
| `engine-docs-implementation/CodeStrata-Engine-MVP-Boundary-and-Native-Analyzer-Specification.md` | `379ec3ce43d0cb3031f9cabac12b52d9f597586de7b46eb1c4d44985bbeed360` |
| `engine-docs-implementation/CodeStrata-Engine-Measurement-Metrics-and-Evidence-Contract.md` | `18f8b0b1b18ea3afb45a2e1fde355a11bf8f288d4308301f97bc8fef0165f085` |
| `engine-docs-implementation/CodeStrata-Engine-Team-Execution-and-Quality-Gates.md` | `a0246232defc01fc3ee83da2347d84486e3f43969c728d9adb8f9ee7796d9653` |

## Git identity enforcement hooks (engine-docs-implementation/git-hooks/)

| Relative path | SHA-256 |
|---|---|
| `engine-docs-implementation/git-hooks/commit-msg` | `e1013d766051613fdfb1f76d8099a66ef80e2a07a7e34bcc8af51b113ae6100b` |
| `engine-docs-implementation/git-hooks/pre-commit` | `33383ea3a6107fa9cb63e5f8aeb744a1e4020d14156ad989c1b2b7bddf27387f` |

## Preflight (00-START-HERE/)

| Relative path | SHA-256 |
|---|---|
| `00-START-HERE/G00-preflight-and-branch-setup.md` | `2ac7ef72732d88363abe5dc565e3b6126185a4cfc88b99b0e213f9c8251a7cb2` |

## Quality-gate templates (quality-gates/)

| Relative path | SHA-256 |
|---|---|
| `quality-gates/audit-prompt-template.md` | `98196cd5485028bab75f600423467db09bbb66e4bcb72b1c53066bca4b92c4ae` |
| `quality-gates/gate-record-template.md` | `f547be54473035c746f7a3096379e210149a725466acd2dbb3e0aaf2652dbc00` |
| `quality-gates/repair-prompt-template.md` | `1a38a71876cd68883f7156f03b152ffca725ea8e0a284303eb4655dea8c6e100` |

## Split engineer prompts (by-engineer/)

| Relative path | SHA-256 |
|---|---|
| `by-engineer/Engineer-A/Group-1-G00/P02-E01.1.md` | `310b21e4084276b851170b5e7c5a752d6598f78283965b11e81aa8cdf30867fc` |
| `by-engineer/Engineer-A/Group-1-G00/P05-E01.2.md` | `e3679b7239e283323c1a9f29811e9f26359b9fd83a0012f4c01d3fb7d45be8e5` |
| `by-engineer/Engineer-A/Group-1-G00/P08-E01.3.md` | `2925057b7604a01c8368a067faa4cdc62d9f485bdc09d6c283680ee63ee43175` |
| `by-engineer/Engineer-A/Group-2-G10/P12-E03.1.md` | `93f9ab6acb55962a9a1e4ef5201a6b07f5f4ba0d1d8a2b633414568bc782ec73` |
| `by-engineer/Engineer-A/Group-2-G10/P13-E04.1.md` | `70f518a35440a101dacd9225d7082536d2c57fa14456e754f86f8201131cc124` |
| `by-engineer/Engineer-A/Group-2-G10/P15-E03.2.md` | `883ab72dc6e113dcbcd7cd16a2f77e272bc18a3f768eaf5402879a4d029bc0f8` |
| `by-engineer/Engineer-A/Group-2-G10/P16-E04.2.md` | `2169dc34771e01ea6eff88cf95ed393476912f2ac28e948ee8d14e87b1d8f584` |
| `by-engineer/Engineer-A/Group-2-G10/P17-E03.3.md` | `eb0de5e115e2cdf977c02de62af3047292475931c83fa9cf4d58cf76f627b2d4` |
| `by-engineer/Engineer-A/Group-2-G10/P20-E04.3.md` | `3459c0e8a245b6e347dd92aad690df3cb6ea4bcb370192888c1ca51a87819545` |
| `by-engineer/Engineer-A/Group-3-G20/P23-E07.1.md` | `1844a8f5be736ca7c9d4887d934e772bacaa9bc1ef8031f854d31c14cfe2e9d5` |
| `by-engineer/Engineer-A/Group-3-G20/P26-E07.2.md` | `05d1153e2d6c7c2ca608690ad508eda8dee2115561117f921caa74713d56f488` |
| `by-engineer/Engineer-A/Group-3-G20/P29-E07.3.md` | `bffc36ce13a39a49904a84e2042d0be5a5849c44e81def88e8e76215da3081ae` |
| `by-engineer/Engineer-A/Group-4-G30/P33-E11.1.md` | `cd0f33e0e32d669a7bc8791eb1f3c81c38e2bc23da4b1ee5c85a07508fe3531b` |
| `by-engineer/Engineer-A/Group-4-G30/P36-E11.2.md` | `8775dda42d5738d18e173e2ea27942a505d1cb34fea9d1f108d611d60ec76526` |
| `by-engineer/Engineer-A/Group-5-G40/P46-E11.3.md` | `39c1948f74f42c3c43dd2f48011d0701a71c842319e1b684a3340f0ca0b6c241` |
| `by-engineer/Engineer-B/Group-1-G00/P03-E05.1.md` | `01aeed91a106aef79af9299d6f2670b5932b6ef5d2df49707cab4713588bf7ef` |
| `by-engineer/Engineer-B/Group-1-G00/P07-E05.2.md` | `844b40a970f7e4f2b09447c80b710ef499a2877bb602a52a13c63a3bc0c97266` |
| `by-engineer/Engineer-B/Group-2-G10/P18-E05.3.md` | `4726e9f009360714b8e5778893dc8dfe46b4a72440b299c9ae71f1878085e662` |
| `by-engineer/Engineer-B/Group-2-G10/P19-E06.1.md` | `649a903901c50ec487d16bb1b374a051e87e51acacff97bc031b1156098eeea2` |
| `by-engineer/Engineer-B/Group-3-G20/P22-E06.2.md` | `e01ea74ac052f274584e351fd2badb5cf8ebb42eb803b9590ea14f2b7859bcd7` |
| `by-engineer/Engineer-B/Group-3-G20/P25-E06.3.md` | `c6f5fc7320e3570e8f8815f0110b02cd771de0bd238dacd4b2a5f8244ffded9b` |
| `by-engineer/Engineer-B/Group-3-G20/P27-E08.1.md` | `8e56525ff2747af3efe9a41f9849678c0b1accfe6fa601abbbf8ddd3bb4b23f0` |
| `by-engineer/Engineer-B/Group-4-G30/P31-E08.2.md` | `d9233e4f9a2ede974d87109c8fe894cdf31bc7534b99f42bf1e4633ef3eaa350` |
| `by-engineer/Engineer-B/Group-4-G30/P34-E08.3.md` | `8bed48c1b36273c4136e4c5710214255d306579ba9f8ac1c2392eaa008bd583e` |
| `by-engineer/Engineer-B/Group-4-G30/P37-E13.1.md` | `52009bcf28b8b410c3aeb1c1dca82e13c6b4dd2c79634965322f12eb01dd11ad` |
| `by-engineer/Engineer-B/Group-4-G30/P39-E13.2.md` | `444834b510cf25c6df1a8e325dbbfa2ac0708b2b38b386e5af9e498c26386d30` |
| `by-engineer/Engineer-B/Group-5-G40/P41-E13.3.md` | `338fa282c9f7ab39b9f9075a859e7c29ee60e5e196f872277734504b815457b0` |
| `by-engineer/Engineer-B/Group-5-G40/P43-E14.1.md` | `7689280ea13b21876b1a5687f8ec76e0d3e0b35722899662c62915a97f3ebb1c` |
| `by-engineer/Engineer-B/Group-5-G40/P45-E14.2.md` | `8054d130b209341724ff9de4e51cc153a84b023c18f35b7c68e4d5059e3e39ec` |
| `by-engineer/Engineer-B/Group-5-G40/P47-E14.3.md` | `2ad20e7f8f61dad32903763dc871b8b2bd049521d4f2e7a3d972323825692485` |
| `by-engineer/Engineer-B/Group-5-G40/P48-E14.4.md` | `de2cc0e41ed7d923ec3589a072a4c0e82825deabad343f442ca7c717a5ceb317` |
| `by-engineer/Engineer-C/Group-1-G00/P01-E00.2.md` | `ab078ede87dedc4f8d510b8c0b29d1a6b4140d3e1fd8ddaf3b88e261a307dc4a` |
| `by-engineer/Engineer-C/Group-1-G00/P04-E00.1.md` | `05dcd2ea99168203453df461f029771c1602ed9e6e8dca121f7584a236985fea` |
| `by-engineer/Engineer-C/Group-1-G00/P06-E02.1.md` | `a6dec0a3511ecc01e625f5f993a1718b2dfe7e5b0f98fcb72426f99a550022c6` |
| `by-engineer/Engineer-C/Group-1-G00/P09-E00.3.md` | `1f8e5ec712d7753b797e6c8cf01591c53824e20bd324c667db78be9ac1bc7bf6` |
| `by-engineer/Engineer-C/Group-1-G00/P10-E15.1.md` | `2911d6f0b033833f7d82b85742ef29236f0df308954c2ca35cfb0c81f8664192` |
| `by-engineer/Engineer-C/Group-2-G10/P11-E02.2.md` | `16c8a834ab0747ef53a7d733103851cb1a8a9dd436a0f92f4cd48c31bf22d533` |
| `by-engineer/Engineer-C/Group-2-G10/P14-E02.3.md` | `682e7b1e8fb1b4c9c8361ebe44a00827887625d1e9ac13d254100440b5f595b8` |
| `by-engineer/Engineer-C/Group-3-G20/P21-E09.1.md` | `87302349edb5282d904a2190138000eb4438e44792b9564cfa75e1ffc3def30c` |
| `by-engineer/Engineer-C/Group-3-G20/P24-E09.2.md` | `08b50e9df98aa9c4933ce685a410016af6fe6832295318407f5f4b6de1f87121` |
| `by-engineer/Engineer-C/Group-3-G20/P28-E09.3.md` | `c7edcf98dd588adfaa19c06a582ec5b74befe9f43032455d9d713c4ffd440c35` |
| `by-engineer/Engineer-C/Group-3-G20/P30-E15.2.md` | `dcd78bca8c9ac17289d3e2a782bf3405e73956cf5909063888c7f1d08562bd9f` |
| `by-engineer/Engineer-C/Group-4-G30/P32-E10.1.md` | `3218e5e458f0af772459465efd433e689bca434e9073e774e126f263ca04c188` |
| `by-engineer/Engineer-C/Group-4-G30/P35-E10.2.md` | `3188c2847447a99a1408abe140651c5986f5f4746b16cd5d49b882d828ca53c9` |
| `by-engineer/Engineer-C/Group-4-G30/P38-E10.3.md` | `5d8cc212a02e661d9a0e4c0ddd45d116db5a640e4218954aade51a20f0a83a5b` |
| `by-engineer/Engineer-C/Group-4-G30/P40-E12.1.md` | `5f20a8ab131fe99986867b1d8359542523a46a7c15635fbee5448fc128f96ffa` |
| `by-engineer/Engineer-C/Group-5-G40/P42-E12.2.md` | `63c1de00177637598d9d107d068a1d8494f8f59aeb230f1aa5b9ddc4e3da95d6` |
| `by-engineer/Engineer-C/Group-5-G40/P44-E12.3.md` | `4eb46ed6d7888117359feafed90b3479c46fc731ee44ac5665260d446e124e84` |
| `by-engineer/Engineer-C/Group-5-G40/P49-E15.3.md` | `72ed472dad6ec01a5bc45cb039d86a95f8e862bf86fb34b7e2f09b6123a25e0a` |
| `by-engineer/Engineer-C/Group-5-G40/P50-E16.1.md` | `767fd02500908bbe91ff36a0cb4f8d21bc25804ad560c27b112d32943b1325fc` |
| `by-engineer/Engineer-C/Group-6-G50/P51-E16.2.md` | `681361355afbce32a238bdc13ef15d3ee1eafa513ce1298093fe31006be4d999` |
| `by-engineer/Engineer-C/Group-6-G50/P52-E16.3.md` | `d886c13d0d248010f49e4c0d777cc0a686689f4405a4f89d052b1e830df9b8bd` |

**Total files tracked: 64** (6 specifications + 2 git hooks + 1 preflight + 3 quality-gate templates + 52 split prompts).

To recompute for one section, e.g.: `sha256sum engine-docs-implementation/*.md` or `find by-engineer -name 'P*.md' -exec sha256sum {} \;` from this directory (`engine/docs/implementation/prompts/` once copied per Kickoff Steps Phase 2).
