# Engine validation corpus (E15.1)

**Package revision:** `ENGINE-2026-09-15-R1`  
**Measurement:** M33  
**Story:** E15.1  
**Manifest check:** `PASS`

This file is generated from pinned YAML under
`engine/verification/validation/corpus/`. It does not run the 50 remotes,
does not tune analyzers, and is not G50/G52 release evidence.

## Three tiers

1. **Dogfood** — 1 CodeStrata-owned pin(s), for consistency.
2. **External large** — 50 identified public remotes
   (the launch bar is >= 50). The historical 22-repository catalog is a
   discovery lead only.
3. **Labeled flagship** — 6 independent labels
   that precede tuning.

## Selection criteria

- Minimum GitHub `size` **50000 KiB**.
- Unique canonical clones: True.
- Discovery-22 counts as fifty: False.
- Convenience replacement to hide failures: False.
- Diversity axes: language_group, project_shape, license_family, monorepo_vs_library, retained_vs_unsupported_depth, intentionally_vulnerable_subset.

## Scan policy

- Public scan is **read-only**; assessed repository code is not changed.
- Assessed-project builds, tests, install hooks and silent default-test
  fetches are forbidden.
- Private/customer content is not stored in these manifests.

## Window, inputs, expectations

- History window: 180 days then latest 1000 commits (M24).
- Proposed (unpublished) budgets: <=10k eligible files: 10min/2GiB; <=100k eligible files: 30min/8GiB on 4vCPU.
- Git state: detached HEAD at the pinned SHA; no branch switch of the assessed remote
- Config: Community default YAML rule pack; single YAML runtime boundary
- Feed: pinned offline OSV snapshot from E01.1; no silent online fallback
- Invocation: codestrata assess --repo <checkout> --no-ai; do not execute scanned project tests or builds
- Survival is not analytical correctness. Unknown denominators stay UNKNOWN.
- Failed or unrun checks are never recorded as PASS. Budget overruns never
  silently truncate success.

## Five early representatives

| Role | Repository |
|---|---|
| `supported_java` | `doris` |
| `supported_js_ts` | `typescript` |
| `mixed_build_monorepo` | `vscode` |
| `retained_lower_depth` | `django` |
| `partial_unsupported` | `rust` |

## Dogfood pins

| Id | URL | SHA | License | Size KiB | Language |
|---|---|---|---|---|---|
| `codestrata-engine` | https://github.com/CodeStrata/codestrata-engine | `ca18a660f164f8c2bd9983a81faf1f82094a1abc` | MIT | 4152 | python |

## External large pins

| Id | Repository | SHA | License | Size KiB | Language group | Shape | Depth |
|---|---|---|---|---|---|---|---|
| `doris` | `apache/doris` | `979e053f0802fbc48f83dafe7f713c02968415a8` | Apache-2.0 | 1409196 | java | data_platform | supported_java |
| `spring-framework` | `spring-projects/spring-framework` | `b9fa06291846aa5ca5324e275c3ab263b30f02c2` | Apache-2.0 | 245720 | java | library_framework | supported_java |
| `spring-boot` | `spring-projects/spring-boot` | `adbbf047320013ee42284d6957293aaf75a56ad7` | Apache-2.0 | 219235 | java | library_framework | supported_java |
| `kafka` | `apache/kafka` | `995cfcf99f7917403e030428c00b5c51808ddc61` | Apache-2.0 | 315523 | java | distributed_system | supported_java |
| `elasticsearch` | `elastic/elasticsearch` | `1d90414ee7f7646b30e9fc14bfd6bd83aabb5f40` | NOASSERTION | 1772023 | java | distributed_system | supported_java |
| `flink` | `apache/flink` | `7a80bb45841f9c30917478e1f147d5d6d0872bf7` | Apache-2.0 | 554140 | java | distributed_system | supported_java |
| `cassandra` | `apache/cassandra` | `d48548c7afe91fc654f4dfd518628dd90ab16ccd` | Apache-2.0 | 470321 | java | distributed_system | supported_java |
| `jenkins` | `jenkinsci/jenkins` | `81dc9a3e13a3ec4c4f74bedb772e3382b8de0760` | MIT | 173507 | java | web_application | supported_java |
| `hadoop` | `apache/hadoop` | `a3febb258a28c1023a09ba29bc41c1b98a2c2cc7` | Apache-2.0 | 610016 | java | distributed_system | supported_java |
| `quarkus` | `quarkusio/quarkus` | `34a4722ef14232f218b816f829749ea509a1e262` | Apache-2.0 | 530271 | java | library_framework | partial_framework |
| `typescript` | `microsoft/TypeScript` | `2c99d0883bf82e7d1cd13b18fa418363c72aa5b4` | Apache-2.0 | 2863693 | javascript-typescript | compiler | supported_js_ts |
| `react` | `react/react` | `59aff3e18cb5b3a336c280bbfa57ec37999511b9` | MIT | 1093312 | javascript-typescript | library_framework | supported_js_ts |
| `nextjs` | `vercel/next.js` | `7b58e5880cbac52ec705ee2039e963c32a854951` | MIT | 2569104 | javascript-typescript | web_framework | partial_framework |
| `vscode` | `microsoft/vscode` | `d3c24c3c4d7efab36b37acb1e91d9502c0c35b28` | MIT | 1469881 | javascript-typescript | mixed_monorepo | mixed_build_monorepo |
| `angular` | `angular/angular` | `7569a02d2961155cc32b9491918bde8ae4c47616` | MIT | 658589 | javascript-typescript | mixed_monorepo | partial_framework |
| `node` | `nodejs/node` | `e98208bc27ef1f69318f3bfee96310ffadf8272b` | NOASSERTION | 1602898 | javascript-typescript | mixed_native | mixed_build_monorepo |
| `webpack` | `webpack/webpack` | `1d75746db30fdaa6106340b30ae9b07bf092cff6` | MIT | 105588 | javascript-typescript | library_framework | supported_js_ts |
| `react-native` | `react/react-native` | `af4d8eb08ad0d73f98adaa2cab5f4516ca74e875` | MIT | 983035 | javascript-typescript | mixed_native | mixed_build_monorepo |
| `babel` | `babel/babel` | `fd665901dece022a0eda2ae7adda03bc9baabd5e` | MIT | 146625 | javascript-typescript | mixed_monorepo | supported_js_ts |
| `jest` | `jestjs/jest` | `202dd8a14777c270607c2416bd5034c3c0abc984` | MIT | 323422 | javascript-typescript | mixed_monorepo | supported_js_ts |
| `django` | `django/django` | `862ade3409ceaa8ec5305e6f5aa26ee0e553cf02` | BSD-3-Clause | 282872 | python | web_framework | retained_lower_depth |
| `gradio` | `gradio-app/gradio` | `15ce43720d1611f44e4661c74d604eabe0d04daf` | Apache-2.0 | 360060 | python | web_application | retained_lower_depth |
| `pandas` | `pandas-dev/pandas` | `cf85d5d203826cab8e164e3ccbe755e49f328d99` | BSD-3-Clause | 413185 | python | library_framework | retained_lower_depth |
| `scikit-learn` | `scikit-learn/scikit-learn` | `7a6ed871e03e95de276b0bc354ffb21e8399de59` | BSD-3-Clause | 187556 | python | library_framework | retained_lower_depth |
| `transformers` | `huggingface/transformers` | `c587bc884db2c2e31fc2b8102314656b17aa07b1` | Apache-2.0 | 518592 | python | library_framework | retained_lower_depth |
| `ansible` | `ansible/ansible` | `1a4c6636245e72e64422f3e83e264f32c304fb65` | GPL-3.0 | 266031 | python | automation | retained_lower_depth |
| `home-assistant` | `home-assistant/core` | `2329db5a05085ef6d7b8e6b00eb380a9a4ad4091` | Apache-2.0 | 898229 | python | web_application | retained_lower_depth |
| `airflow` | `apache/airflow` | `224d34121c877c21e8dee97520b05c02f578a839` | Apache-2.0 | 715910 | python | mixed_monorepo | retained_lower_depth |
| `bagisto` | `bagisto/bagisto` | `9beff85ece6fe13378a97e6f84765b50647d3327` | MIT | 416988 | php | web_application | retained_lower_depth |
| `moodle` | `moodle/moodle` | `e68a1418bea512dd5992c29eb9e36570a3844e94` | GPL-3.0 | 971433 | php | web_application | retained_lower_depth |
| `laravel-framework` | `laravel/framework` | `1d9727160ad440d1ccf2fdcbb7e4f4f36efae212` | MIT | 105069 | php | library_framework | retained_lower_depth |
| `magento2` | `magento/magento2` | `874f1f5cdf3bc52b61c3d66becf159cc16345d7a` | OSL-3.0 | 751167 | php | web_application | partial_framework |
| `phpmyadmin` | `phpmyadmin/phpmyadmin` | `65f19ca48edf8f8d024447e136f8728fceb2a74c` | GPL-2.0 | 2537937 | php | web_application | retained_lower_depth |
| `nextcloud` | `nextcloud/server` | `be4ffd4257b40fcbbcd116d41d85218acbd54e2b` | AGPL-3.0 | 7151303 | php | web_application | retained_lower_depth |
| `wordpress` | `WordPress/WordPress` | `e2ce85670c84edceb36ed5762e532ca16c0276d9` | NOASSERTION | 712963 | php | web_application | partial_framework |
| `aspnetcore` | `dotnet/aspnetcore` | `1fcd7ef305697a1888f3ede076010350ae9f4f8d` | MIT | 396311 | csharp | library_framework | retained_lower_depth |
| `dotnet-runtime` | `dotnet/runtime` | `7adc767a7bb3c41986db17f10a6369800501a624` | MIT | 1241346 | csharp | mixed_monorepo | retained_lower_depth |
| `roslyn` | `dotnet/roslyn` | `3c9fedee40c44979ca893b6490ad5748bbb137b5` | MIT | 2689724 | csharp | compiler | retained_lower_depth |
| `powershell` | `PowerShell/PowerShell` | `84a93015104945c16b7aa69ee67a82cb1e6499dc` | MIT | 109184 | csharp | tool | retained_lower_depth |
| `kubernetes` | `kubernetes/kubernetes` | `96b5e4e3ae3f8d7aa50d360cf57f01eaba61f855` | Apache-2.0 | 1524207 | go | distributed_system | partial_unsupported |
| `go` | `golang/go` | `46f508b3aa365918ac78a63340ce2343306835af` | BSD-3-Clause | 457161 | go | compiler | partial_unsupported |
| `terraform` | `hashicorp/terraform` | `78194be60cdab9c71ea1caf5e5c0b4d96e2c3691` | NOASSERTION | 359215 | go | tool | partial_unsupported |
| `prometheus` | `prometheus/prometheus` | `296080c0a504ea0e72941ef16143f0a9702b137b` | Apache-2.0 | 290558 | go | distributed_system | partial_unsupported |
| `rust` | `rust-lang/rust` | `971903d9aee24befd88423f42826c232e27c8190` | Apache-2.0 | 1000621 | rust | compiler | partial_unsupported |
| `deno` | `denoland/deno` | `abd22074e47c6a5cd14e9e4e84743f084aa5a575` | MIT | 250569 | rust | mixed_native | partial_unsupported |
| `rails` | `rails/rails` | `8b5f77d2a26a4ed1f1ba16385b88f178ced27fc5` | MIT | 289650 | ruby | web_framework | partial_unsupported |
| `spark` | `apache/spark` | `a76032ef17f0d7d05fd55891f007a3a8cad3267e` | Apache-2.0 | 612080 | scala | distributed_system | partial_unsupported |
| `kotlin` | `JetBrains/kotlin` | `32e72c24aa3530144f50bfe781622bdc5fa4d4a7` | NOASSERTION | 4355671 | kotlin | compiler | partial_unsupported |
| `juice-shop` | `juice-shop/juice-shop` | `1618a611b173b4bf114028e6e02549950606e29d` | MIT | 305008 | javascript-typescript | intentionally_vulnerable | flagship_labeled |
| `vite` | `vitejs/vite` | `e9078f865cdff6bed77cd729214a7e2868f126b5` | MIT | 74665 | javascript-typescript | library_framework | supported_js_ts |

## Discovery lead (not the 50-large bar)

Source: `validation/repository-catalog/catalog.json (outside Engine; copied as a lead)`. Count: 22.
Meets 50-large bar: False.

## Independent labels

Fixture labels were authored before analyzer tuning.
They are not Engine output.

### Flagship

- `juice-shop-owasp-classes` (labeled-flagship) expected `labeled`: Public intentionally-vulnerable app. Labels are class-level, not a run of the Engine.
- `planted-secret-fixture` (labeled-flagship) expected `find`: Synthetic token marked planted-fixture; not a live credential.
- `planted-vulnerable-dependency` (labeled-flagship) expected `find_or_unknown_if_feed_missing`: Old lodash pin for later feed matching. Missing feed => UNKNOWN, never clean PASS.
- `planted-architecture-cycle` (labeled-flagship) expected `find`: Two Java packages import each other. Independent expected cycle.
- `unsupported-rust-snippet` (labeled-flagship) expected `UNKNOWN`: Rust-only snippet. Unsupported language is not successfully assessed.
- `nodegoat-known-issues-not-large` (labeled-flagship) expected `labeled`: Small known-issues app. Discovery lead only; excluded from external-large by size.

### Adversarial / operational (M33)

- `resource-exhaustion` (resource-exhaustion) expected `ERROR`
- `corruption` (corruption) expected `ERROR`
- `repeat-variation` (repeat-variation) expected `equal_or_fail`
- `sigint-sigterm-hard-kill` (sigint-sigterm-hard-kill) expected `cancelled_or_error`
- `disk-full` (disk-full) expected `ERROR`
- `output-collision` (output-collision) expected `ERROR`
- `concurrent-reader` (concurrent-reader) expected `stable_read`
- `retention-active-baseline` (retention-active-baseline) expected `retained`
- `audit-redaction` (audit-redaction) expected `redacted`

## Manifest check summary

All 363 manifest checks PASS.
