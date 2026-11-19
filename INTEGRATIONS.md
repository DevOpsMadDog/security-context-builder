# Integration guide: cloud and application security context

Research date: **2 November 2026**. This guide distinguishes documented upstream capabilities from the proposed platform integration. It accompanies a starter, not a deployed security service.

## 1. Delivery status and integration boundary

| Status | Meaning in this guide |
| --- | --- |
| Verified documentation | Official documentation or upstream repository files were read. This establishes a documented interface, not successful operation in your environment. |
| Offline implementation | Any local parsing or rendering implemented elsewhere in this starter. Consult its README and test results for its exact coverage. |
| Proposed integration | Authentication, collection, scheduling, correlation, repository publication or remediation orchestration still to implement against your accounts. |
| Not executed | No AWS account assessment, Threat Composer AI generation, Codex Security scan, Claude scan, vendor API collection, code fix or deployment was run during this research. |

Use existing scanners and repair engines. Build the maintained relationship between a finding, the affected deployment, its source and infrastructure commits, the relevant threat/control, and a verified fix. Keep native evidence alongside a normalized representation; conversion must not silently erase scanner-specific detail or unsupported records.

## 2. AWS Threat Composer

[Threat Composer](https://github.com/awslabs/threat-composer) is a public Apache-2.0 project. Its README documents a stable web application and VS Code extension, JSON/Markdown/DOCX/PDF export, and an **experimental** AI CLI. Therefore, a custom Markdown exporter is optional: use the native exports where suitable, and compile smaller task-specific summaries when combining them with cloud and scanner context.

The [AI CLI guide](https://github.com/awslabs/threat-composer/blob/main/docs/AI-CLI-MCP.md) documents source analysis, architecture/dataflow diagrams, STRIDE analysis and structured threat-model generation through Amazon Bedrock. The standalone CLI and optional MCP interface share the underlying workflow. This design can use the CLI directly.

Documented basic invocation, with placeholder paths and AWS profile/region names:

```bash
threat-composer-ai-cli /path/to/codebase \
  --output-dir /path/to/analysis-results \
  --aws-profile approved-profile \
  --aws-region approved-region
```

The upstream installation route uses `uv tool install` from the repository's `packages/threat-composer-ai` subdirectory. Before production installation, select a reviewed repository revision, lock dependencies, and verify runtime requirements. The documented requirements include Python, AWS credentials with Bedrock access, and Graphviz for diagrams. Inference incurs usage charges. No installation or inference is performed by this guide.

Expected native output includes `threatmodel.tc.json`, component JSON, assumptions, run metadata and session/log artifacts. Treat the generated model as a draft: confirm deployment facts, identity boundaries, data classification, non-code dependencies and accepted risks with the application owner.

### Native schema and correlation

The [v1 schema](https://github.com/awslabs/threat-composer/blob/main/schemas/threat-composer-v1.schema.json) includes `applicationInfo`, `architecture`, `dataflow`, `assumptions`, `threats`, `mitigations`, `assumptionLinks` and `mitigationLinks`. It requires the schema identifier and disallows arbitrary top-level properties. Preserve the native file and put additional deployment/evidence relationships in a sidecar or the knowledge database.

Native threat-to-mitigation links use `mitigationId` and `linkedId`; assumption links also include `type`, with `Threat` or `Mitigation`. Preserve UUIDs. A native status such as `threatResolved` is an authoring decision, not evidence that a deployed remediation passed verification. Record those states separately.

Proposed adapter contract: accept a schema-valid `.tc.json`, retain its hash and source revision, extract native IDs and links, then generate a scoped Markdown view with explicit assumptions and unresolved questions. Retain human amendments on later generation runs.

## 3. OpenAI Codex Security

The supplied [openai/codex-security repository](https://github.com/openai/codex-security) is public and Apache-2.0 licensed. It documents a CLI, TypeScript SDK and GitHub Action. The [official product guide](https://learn.chatgpt.com/docs/security) distinguishes local plugin/CLI/SDK use from the optional Codex Security Cloud product. Repository access and package installation do not establish your account's inference permissions or Cloud access.

The project supports discovery, imported findings, source assessment, patches, fix assessment, saved threat models and report exports. Use these capabilities as the first repair adapter; keep the platform's evidence model independent of this provider.

### Documented CLI entry points

These examples follow the [CLI reference](https://learn.chatgpt.com/docs/security/cli/reference). Paths, scan IDs and repository names are placeholders; the commands were not executed.

```bash
npm install --global @openai/codex-security
codex-security login
codex-security scan .
```

Use an explicitly selected package version in a reproducible deployment. The documentation also supports `npx @openai/codex-security` and the short alias `cs`. The researched runtime requirements are Node.js 22.13.0 or later within 22.x, or Node.js 24/26, plus Python 3.10 or later; Python 3.10 additionally needs `tomli`. Recheck the selected release before provisioning workers.

### Context and multiple repositories

The CLI accepts repeated `--knowledge-base PATH` arguments. The documented formats include UTF-8 text, JSON/SARIF, PDF, DOCX and directories. Pass the relevant architecture, cloud posture, threats and evidence explicitly. Do not rely on arbitrary Markdown being automatically loaded.

Place immutable app and infrastructure checkouts under a parent directory. For this example, `/work/application/app` and `/work/application/infra` are separate checkouts; `/work/context` and `/work/results` are outside them:

```bash
codex-security scan /work/application \
  --mode deep \
  --path app/src \
  --path infra \
  --knowledge-base /work/context/architecture.md \
  --knowledge-base /work/context/cloud-posture.md \
  --knowledge-base /work/context/threat-model.md \
  --knowledge-base /work/context/relevant-findings.json \
  --output-dir /work/results/run-001 \
  --json
```

The [cross-repository guide](https://github.com/openai/codex-security/blob/main/sdk/typescript/docs/cli.md#review-one-system-across-repositories) documents this parent-directory approach. Scope paths are relative to the scan root. Record each child repository's URL, commit and working-tree state yourself: a non-Git parent is a directory snapshot, not automatically a separately pinned revision for every child. Keep inputs unchanged during a scan or resume. Include both sides of boundaries being assessed and state missing-service coverage explicitly.

**Output requirement:** results must be outside the scanned directory and outside any enclosing Git worktree. Use a new/empty output directory. This prevents generated reports from becoming part of the scanned input.

### SDK interface

The upstream README documents this minimal TypeScript interface:

```typescript
import { CodexSecurity } from "@openai/codex-security";

const security = new CodexSecurity();
try {
  const result = await security.run("/path/to/repository");
  console.log(result.reportPath);
} finally {
  await security.close();
}
```

Use the selected version's [SDK guide](https://github.com/openai/codex-security/blob/main/sdk/typescript/README.md) for configuration and result types. Do not invent wrapper method names or assume a generic HTTP scanning API matches the SDK.

### Existing scanner imports

The [upstream import index](https://github.com/openai/codex-security/blob/main/docs/scanner-imports/README.md) currently documents Amazon Inspector Code Security, Black Duck SCA, Endor Labs, GitHub code scanning/Dependabot/advisories, OpenGrep, Semgrep Code, Snyk Open Source, SonarQube Cloud, Veracode Static Analysis and Wiz. Reuse those readers where the exact report type matches.

The documented external-import feature flag is:

```bash
export CODEX_SECURITY_ENABLE_EXTERNAL_IMPORTS=1
```

Follow each provider's own guide for its import command, allowed input, repository/ref selection and source key. Preview with that command's `--dry-run` option, inspect the accepted/excluded records, then save only the reviewed selection. Native imports are provider-specific: a Wiz package-vulnerability reader does not establish support for every Wiz cloud-risk object. Inspector Code Security import does not imply support for every Inspector finding class.

Imported findings begin as `not_assessed`. Preserve that distinction. A source tool's severity, an import result and a later source assessment are different observations.

### Outputs, patching and verification

Saved artifacts can include `scan-manifest.json`, `findings.json`, `report.md`, `threatmodel.md`, supporting evidence and SARIF. Retain artifact hashes, producer version, scope, exclusions and unresolved work. A completed scan does not imply exhaustive coverage.

Documented follow-up examples:

```bash
codex-security export --scan SCAN_ID --artifact threat-model --output threatmodel.md
codex-security export --scan SCAN_ID --export-format json --output findings.json
codex-security patch --scan SCAN_ID --severity high --json
codex-security verify-fix --scan SCAN_ID --json
```

Run exports from a private results location and patches only in a disposable, authorized source checkout. Upstream also documents `--create-pr` for draft PR creation; the starter does not enable it automatically.

The standalone `validate` command is a read-only source assessment: it does not build or execute the application, run tests/PoCs, or contact services. `verify-fix` distinguishes assessed-fixed, still-vulnerable and inconclusive outcomes, but model assessment alone is insufficient release evidence. Run independent application/security regression tests and IaC checks; after deployment, recheck the originating source and affected cloud resource. Keep scan findings-policy failures distinct from execution errors. Never interpret “finding absent from the next scan” as proof of correction.

## 4. Claude alternatives

[Claude Code Security Reviewer](https://github.com/anthropics/claude-code-security-review) documents a PR review action and `/security-review`. It supports custom security scan instructions, filtering instructions, a JSON result path and finding count. A user can subsequently request a targeted fix in Claude Code. This is an alternative repair/review adapter, not a requirement to replace the canonical evidence store.

Its README explicitly states that the action is not hardened against prompt injection and should review trusted PRs. Use a trusted workflow definition, a reviewed Action commit, minimal credentials and isolated execution. Do not copy its floating `@main` example unchanged into an enterprise workflow.

[Claude Security](https://support.claude.com/en/articles/14661296-use-claude-security) is a separate Enterprise public beta documented with cross-repository projects, continuous scans, editable threat models, patch handoff and API/webhooks. Evaluate it if the organization has access; do not assume an individual Claude Code subscription provides these capabilities.

## 5. Connector mapping targets

The table describes proposed integration boundaries. It does not claim these vendor collectors are implemented or connected.

| Source category | First target | Retain and correlate | Implementation boundary |
| --- | --- | --- | --- |
| SAST | Supported Semgrep/OpenGrep/SonarQube/Veracode/GitHub exports | Native finding ID, rule/CWE, repository/ref, file/symbol and source evidence | Reuse an exact supported Codex reader; otherwise normalize a documented native export. |
| SCA | Supported Snyk/Dependabot/Black Duck/Endor exports | Package identity/version, vulnerability, dependency path, manifest/lockfile and scanner verdict | Keep package identity separate from deployment identity; correlate image/SBOM/build provenance. |
| CNAPP/cloud posture | Security Hub CSPM ASFF; supported Wiz report types | Account/region/resource ID, control, timestamps, native severity, status and exposure evidence | ASFF is a documented AWS format; other CNAPP products need their own scoped adapter. |
| XDR | Microsoft Defender XDR incidents | Incident/alert IDs, affected entities, observed/updated time, source investigation state | Proposed read-only collector; an incident is contextual evidence, not automatically a code flaw. |
| SIEM | Bounded Splunk search results | Query/version, time range, event/alert identity, asset IDs and evidence references | Proposed scheduled query/export adapter; restrict the search scope and preserve query provenance. |
| Deployment/ownership | CI deployment manifest and reviewed service catalog | Image digest, app/infra commit, resource ID, application ID and owner | The key bridge from a runtime observation to the correct patch target. |

[AWS documents ASFF](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-findings-format.html). [Defender's incident API](https://learn.microsoft.com/en-us/defender-xdr/api-list-incidents) documents related alerts/entities and update-based retrieval; its current guidance also points toward Microsoft Graph security APIs. [Splunk documents REST export](https://help.splunk.com/en/splunk-enterprise/search/search-manual/10.6/export-search-results/export-data-using-the-splunk-rest-api). Select the supported interface for the customer's actual product/version before coding a collector.

Every collector needs pagination, retry/backoff, rate limits, update cursors, deletion/tombstone handling, idempotency and tenant isolation. Names and IP addresses alone are weak ownership keys; prefer deployment IDs and stable resource identifiers. Record uncertain matches as hypotheses.

## 6. Safe repository context and knowledge retention

Use reviewed `AGENTS.md`/`CLAUDE.md` instructions for workflow rules and pointers. Current [Codex guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md) and [Claude memory guidance](https://code.claude.com/docs/en/memory) describe project instruction loading; Claude also supports `AGENTS.md`. Instructions are not executable authorization controls. Enforce permissions through the runner, identity policy, protected workflows and repository controls.

Generated `docs/security/*.md` files should contain application-scoped summaries and evidence references. Keep raw sensitive logs, credentials and unrestricted incident records outside Git. Treat scanner descriptions, issue text, code comments and log payloads as untrusted data; never promote them into trusted operator instructions.

A context snapshot should record source IDs/hashes, application/environment, account/region, app/infra commits, observation/expiry times, schema and producer versions, coverage, classification and review state. A recently rendered Markdown file can still contain stale evidence. Invalidate or flag affected facts when source, deployment, IaC or evidence changes.

Retain fix history as structured records: the original finding, applicable preconditions, patch, tests and their exact revisions, review outcome, deployment identity, source recheck and rollback/reopening events. These records support retrieval and later model evaluation. An accepted PR is not automatically a successful training label; require the chosen verification standard first.
