# Enterprise AppSec Agent — Design and Runnable Foundation

Prepared on 2 November 2026 for an enterprise AppSec engineering system that learns architecture and requirements, reconstructs applications, correlates cloud/code findings, repairs through OpenSpec, verifies behaviour in controlled environments and preserves long-term engineering experience.

## Reference implementation patterns

- **[Pattern1 — Two Azure DevOps repositories, Terraform and AWS ECS Fargate](patterns/pattern1/README.md)**: Node.js application in vulnapp-app, Terraform/IaC in vuln-app-infra, approved Azure Pipelines build/deploy/context jobs, post-deploy ECS/ALB/WAF provenance, synthetic Veracode/Prisma/Inspector evidence and a working canonical-bundle assembly example. This pattern is a reference and has not been deployed.

## Start here

Read [ENTERPRISE_APPSEC_BLUEPRINT.md](ENTERPRISE_APPSEC_BLUEPRINT.md) for the complete enterprise design. It reflects the expanded goal: versioned specification libraries owned by EA/technical leads, application and cloud readers, security-tool adapters, repair/test workers, local and cloud sandbox verification, and a durable knowledge base.

The included Python prototype demonstrates one foundational component: converting a scoped canonical evidence bundle into application/infrastructure Markdown, per-finding packets and a searchable SQLite snapshot. It is a reference implementation for that boundary, not a complete autonomous AppSec product.

## Deliverables

| File | Contents |
| --- | --- |
| [ENTERPRISE_APPSEC_BLUEPRINT.md](ENTERPRISE_APPSEC_BLUEPRINT.md) | Full system, ownership, reverse engineering, standards adoption, worked example and staged build. |
| [OPENSPEC_AND_ENTERPRISE_STANDARDS.md](OPENSPEC_AND_ENTERPRISE_STANDARDS.md) | Current OpenSpec interfaces, Stores beta, versioned pack design, adoption locks and authorization-fix example. |
| [APPSEC_SKILLS.md](APPSEC_SKILLS.md) | Ten runtime-neutral AppSec workflow specifications with inputs, procedures, outputs and acceptance criteria. |
| [SANDBOX_AND_VERIFICATION.md](SANDBOX_AND_VERIFICATION.md) | Local/cloud test fidelity, functional preservation, independent checks, isolation and lifecycle. |
| [KNOWLEDGE_AND_SMALL_MODELS.md](KNOWLEDGE_AND_SMALL_MODELS.md) | Long-lived experience model, failures, revalidation, retrieval, smaller models and evaluation. |
| [AWS_POSTURE_AND_COMPLIANCE.md](AWS_POSTURE_AND_COMPLIANCE.md) | Verified AWS service capabilities, limitations, evidence collection and onboarding. |
| [INTEGRATIONS.md](INTEGRATIONS.md) | Threat Composer, Codex Security, Claude and scanner adapter integration details. |
| [REPO_CONTEXT_CONTRACT.md](REPO_CONTEXT_CONTRACT.md) | Generated documents, canonical evidence, instructions, manifests and publishing boundaries. |
| [ARCHITECTURE_BLUEPRINT.md](ARCHITECTURE_BLUEPRINT.md) | Detailed design of the evidence/context layer. |
| [context_compiler.py](context_compiler.py) | Python standard-library offline compiler and query tool. |
| [examples/demo-bundle.json](examples/demo-bundle.json) | Explicitly synthetic input containing two findings and one historical example. |
| [tests/test_context_compiler.py](tests/test_context_compiler.py) | Sixteen tests for the implemented boundary. |

## Implemented versus designed

| Capability | Current state |
| --- | --- |
| Single tenant/app/environment input validation | Implemented and tested. |
| Exact repository SHA and ownership consistency | Implemented input checks; source assertions are not authenticated. |
| Source freshness and unknown control handling | Implemented at compile time and rechecked for fix retrieval. |
| Generated app/infra Markdown and finding packets | Implemented with stable scoped IDs and escaped evidence blocks. |
| SQLite fix retrieval | Implemented exact scope filters and literal substring matching. |
| Native SARIF/ASFF/OCSF/Threat Composer/Graphify adapters | Documented integration work; not implemented by the prototype. |
| Authenticated multi-tenant access and durable audit history | Production architecture specified; not provided by local scope filters or SQLite snapshots. |
| OpenSpec execution and signed specification acquisition | Designed; no OpenSpec installation or enterprise store created. |
| Autonomous fixes, unit/functional tests for a user app | Workflow specified; no user application was supplied or repaired. |
| Local cloud simulation and real AWS sandbox execution | Architecture specified; no such environment was deployed. |
| Vector retrieval, model serving and fine-tuning | Design and evaluation plan; no embeddings or model inference fabricated. |

## Run the offline example

Requires Python 3.10 or newer, with no third-party packages. Put the Python file and example input in the paths shown above. From this directory:

```bash
python3 context_compiler.py compile \
  --input examples/demo-bundle.json \
  --out ./demo-output \
  --as-of 2026-11-02T02:00:00Z
```

The command prints the generated directory and exact SQLite path. For the unchanged fixture, the scope directory is `725326642122a1a7d1de41a3`:

```bash
python3 context_compiler.py query \
  --db ./demo-output/generated/725326642122a1a7d1de41a3/ledger.sqlite \
  --tenant demo \
  --app claims \
  --environment staging \
  --text encryption \
  --as-of 2026-11-02T02:00:00Z
```

Use the returned path if the scope changes. Omitting query's `--as-of` checks freshness against current UTC. The explicit historical cutoff above makes this synthetic example reproducible. Queries earlier than the stored snapshot are rejected: this prototype does not implement historical time travel.

Expected compile result: two finding packets, one eligible supplied historical example and `verification_performed: false`. The compiler has not executed or independently authenticated the verification described by the fixture. That historical example does not close the current finding.

Generated files include `application.md`, `infrastructure.md`, `findings/<stable-id>.md`, `manifest.json` and `ledger.sqlite`, beneath the tool's managed generated directory. Existing AGENTS.md and CLAUDE.md are preserved.

## Canonical input contract

The sample JSON is the executable contract for this prototype. Upstream adapters must first normalize vendor data into it.

| Field | Purpose |
| --- | --- |
| bundle_version | Must be 1. |
| tenant_id, app_id, environment | Exact scope for the complete bundle. |
| repositories | Stable ID, application/infrastructure role and full 40-character Git SHA. |
| sources | Native reference ID, kind, observed UTC timestamp and configured maximum age; code evidence also has repo/SHA. |
| resources | Internal resource ID, ownership evidence reference and at most one owner per repository role. |
| findings | Native/local ID, source, severity/state, and exact resource or repository/path target. |
| controls | Asserted state and supporting source references; missing/stale support becomes unknown. |
| fixes | Historical attempt, owning repository/SHA, outcome, summary, time and verification references. |

An asserted verified fix needs verification-kind records tied to the exact historical repository and patch SHA, with a supplied passed result. The parser checks consistency, not truth or digital signatures. Real production adapters must authenticate producers and evidence independently.

The prototype uses internal resource identifiers; it is not a complete ARN/deployment graph schema. It has no business-contract inference, graph traversal engine or threat-model parser. Those are described in the enterprise blueprint.

## Validation performed

Executed the following suite successfully: **16 tests passed**. The compile and query CLI examples also ran successfully against the synthetic fixture.

```bash
python3 -m unittest discover -s tests -v
```

Coverage includes ambiguous owners, mismatched source revisions, scope isolation, malformed references, future/stale evidence, missing control evidence, exact verification linkage, literal-query handling, safe generated paths, existing instruction preservation, deterministic reruns, removal of obsolete finding packets and malformed prior manifests. Retrieval now rechecks TTL rather than trusting a cached eligibility flag.

These tests establish behaviour of this small compiler, not security or correctness of a future enterprise agent.

## Prototype limits relevant to production design

SQLite stores the current snapshot, not an append-only evidence history. A source hash provides content identity, not authenticity. Exact tenant filters do not provide user authentication or access control. Markdown escaping does not eliminate semantic prompt injection. The output workflow assumes a trusted local process and no hostile concurrent writer. Evidence time-to-live is supplied input and must be governed by trusted policy in production.

The compiler performs no network calls, cloud actions, model inference, application builds, security scanning, patch generation or deployment. Vendor command examples in the documents are sourced integration guidance rather than executed integrations.

## First real enterprise pilot

Choose one app/infra repository pair, one supported language/framework, one business flow, one cloud architecture profile, a small approved standards pack and one representative vulnerability class. Supply deployment provenance plus relevant code/cloud findings. Then implement and prove the complete flow on that bounded target: standards adoption, reconstruction, OpenSpec change, patch, independent local/cloud checks, review, deployment and outcome capture.

Required target inputs are repository URLs/branches, application stack, AWS account/Region/environment scope, a representative scanner export and an initial EA/tech-lead standard or approved draft. This provides a concrete pilot without assuming access or inventing application facts.
