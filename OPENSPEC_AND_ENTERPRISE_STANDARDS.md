# OpenSpec and versioned enterprise standards

Research date: **2 November 2026**. This design supports an enterprise AppSec agent that learns application architecture, consumes standards approved by enterprise architects and technical leads, prepares repairs with tests, and preserves institutional knowledge across many years.

**Status:** upstream interfaces were researched through the GitHub connection; no OpenSpec installation, store registration, application analysis, test execution or repository mutation was performed. All organization-specific examples below are proposals. They are not built-in OpenSpec policy fields or claims about an existing application.

## 1. What current OpenSpec already provides

The public MIT-licensed [Fission-AI/OpenSpec repository](https://github.com/Fission-AI/OpenSpec) describes spec-driven development for existing and new applications. The latest release observed was [v1.16.0, published 30 October 2026](https://github.com/Fission-AI/OpenSpec/releases/tag/v1.16.0); the observed main revision was `27c0515724decc633818c735ee596481eec78a8b`. Pin a reviewed release for an implementation; reassess beta interfaces when upgrading.

| Need | Upstream capability | Enterprise work still required |
| --- | --- | --- |
| Durable requirements and change plans | Main specs, change-local deltas, proposal/design/tasks and archive | Requirement ownership, applicability, release/adoption policy and long-term evidence lifecycle |
| Shared standards across repositories | **Stores, in beta**, and read-only references | Verified download, immutable version locks, signatures, approved publishers and upgrade management |
| App and infrastructure coordination | Shared planning store plus separately scoped component changes | Deploy/merge ordering, task routing, compatibility checks and transaction/rollback strategy |
| Customized engineering workflow | Project context/rules and custom artifact schemas | Independently enforced security decisions and proof that required checks ran |
| Implementation review | Advisory verification of completeness, correctness and coherence | Actual test execution, result authenticity, failure handling and deployment rechecks |

This materially reduces what needs building. Reuse OpenSpec's plans, spec references and change lifecycle. Add the enterprise control plane around standards distribution, adoption and evidence.

## 2. Native repository shape and workflow

The [default schema](https://github.com/Fission-AI/OpenSpec/blob/main/schemas/spec-driven/schema.yaml) defines these artifacts:

| Native path | Role |
| --- | --- |
| `openspec/config.yaml` | Project context, schema selection, artifact rules and optional store references |
| `openspec/specs/<capability-path>/spec.md` | Current reviewed requirements for a capability |
| `openspec/changes/<change-id>/proposal.md` | Why the change is needed, capability changes and impact |
| `openspec/changes/<change-id>/specs/<capability-path>/spec.md` | Requirement delta for the change |
| `openspec/changes/<change-id>/design.md` | Technical approach, decisions and tradeoffs |
| `openspec/changes/<change-id>/tasks.md` | Tracked implementation and verification tasks |
| `openspec/changes/<change-id>/.openspec.yaml` | Change metadata, including schema selection |
| `openspec/changes/archive/<date>-<change-id>/` | Archived change and its rationale |
| `openspec/schemas/<schema-name>/schema.yaml` | Optional custom workflow definition with adjacent templates |

Capability paths may be nested. Reuse the actual existing capability ID instead of inventing a near-duplicate. Read the full existing requirement and scenarios before modifying them.

The [command guide](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md) documents the core assistant workflow: `/opsx:explore`, `/opsx:propose`, `/opsx:apply`, `/opsx:update`, `/opsx:sync` and `/opsx:archive`. Codex uses skill invocations such as `$openspec-propose`; Claude uses the canonical slash-command spelling. These are assistant commands, not shell subcommands.

The expanded profile includes `/opsx:verify`; enable the desired workflows through `openspec config profile`, then refresh project integrations with `openspec update`. A suitable organizational lifecycle is proposal, reviewed spec/design, implementation plus tests, independent evidence checks, PR review, archive and deployment confirmation. OpenSpec itself remains flexible; enterprise release gates come from CI and policy.

Documented CLI inspection examples:

```bash
openspec list --specs
openspec new change enforce-claim-authorization
openspec status --change enforce-claim-authorization --json
openspec instructions apply --change enforce-claim-authorization --json
openspec validate enforce-claim-authorization --strict
```

Use these only inside an initialized, intentionally selected project. For a registered store, use the documented `--store <id>` selector on commands that support it. Inspect the returned root so the workflow acts on the intended planning repository.

### Delta semantics matter

Use `ADDED`, `MODIFIED`, `REMOVED` and `RENAMED Requirements` appropriately. A MODIFIED block must contain the complete updated requirement and retained scenarios; partial text can discard requirements during synchronization. Scenarios use `#### Scenario:` and concrete GIVEN/WHEN/THEN steps. The [spec-writing guide](https://github.com/Fission-AI/OpenSpec/blob/main/docs/writing-specs.md) treats specs as observable behavior; implementation choices belong in design/tasks.

`openspec validate` checks document/change validity. It does not prove application behavior or organizational compliance. The upstream [verification skill](https://github.com/Fission-AI/OpenSpec/blob/main/skills/openspec-verify-change/SKILL.md) explicitly describes verification as advisory and labels missing evidence “Not verified.” Require independent execution records before claiming unit, functional or security tests passed.

## 3. Shared standards: use Stores, then add controlled distribution

The [Stores guide](https://github.com/Fission-AI/OpenSpec/blob/main/docs/stores-beta/user-guide.md) documents a standalone Git planning repository with `.openspec-store/store.yaml` identity and ordinary `openspec/specs` and `openspec/changes` directories.

For the requested enterprise model, prefer local app/infra planning roots that **reference** the standards store:

```yaml
# Native OpenSpec fields: application/openspec/config.yaml
schema: spec-driven
references:
  - id: enterprise-standards
    remote: git@github.com:example-org/enterprise-standards.git
context: |
  Use the approved standards revision verified by the enterprise launcher.
  Record each applicable requirement and its acceptance evidence.
  Treat reverse-engineered behavior as observed until reviewed by its owner.
rules:
  proposal:
    - Cite applicable standard requirement IDs and proposed exceptions.
  specs:
    - Preserve authorized user behavior and describe security failure cases.
  tasks:
    - Map each changed requirement to executable checks and retained results.
operations:
  apply:
    guidance:
      - Run focused regression checks before broader integration tests.
```

The remote URL is a placeholder. These prompt inputs guide agents; they do not implement the lock verification or approval policy described next.

`references:` retains the local planning root and exposes an index of read-only upstream specs. By contrast, `store: enterprise-standards` routes planning commands into the central store when root-resolution rules select it. Do not use that pointer merely to consume standards: a service repair normally belongs in the service repository.

Native documented setup includes explicit Git cloning followed by `openspec store register /path/to/checkout`. **OpenSpec never clones, pulls or pushes stores itself.** References are indexed from the registered files on disk. One checkout per store ID is supported per machine. Worksets help open several folders but do not route tasks into component repositories or grant edit permissions.

### Proposed enterprise spec-pack contract

Treat a released pack like a software dependency. EA/technical leads own requirements and applicability; AppSec owns security acceptance criteria; platform teams maintain reusable check adapters. A pack should carry a version, immutable Git commit and content digest, owner, supported environments, dependencies, compatibility notes, requirement IDs, test obligations and reviewed release notes.

Keep machine-readable enforcement metadata separate from natural-language guidance. The following **proposed lockfile** is not an OpenSpec configuration schema:

```json
{
  "schema_version": "1",
  "application_id": "claims-api",
  "packs": [
    {
      "id": "enterprise-standards",
      "version": "2.3.1",
      "commit": "<reviewed-40-character-commit>",
      "content_digest": "sha256:<verified-content-digest>",
      "attestation_ref": "<immutable-attestation-reference>",
      "requirements": ["AUTHZ-017", "AUDIT-004"]
    }
  ]
}
```

The launcher/CI resolver must fetch only approved sources, resolve the exact revision, verify content and signature against publisher identities trusted outside the pack, validate dependency locks, and materialize a read-only checkout. It then registers that checkout for the run and checks actual revision/hash against the committed adoption lock before model access. A mutable tag or branch name alone is insufficient. A valid signature proves the expected publisher signed those bytes; it does not prove that this application has approved adopting them.

Use isolated per-run environments to avoid different applications racing over the same store registration. A developer's stale store checkout must produce an explicit mismatch; never silently substitute its contents. No documented native package-version resolver, signature checker or reference lockfile was established in the inspected OpenSpec interfaces, so these are enterprise components to implement.

## 4. Applicability, precedence and exceptions

Avoid resolving policy conflicts through whichever document was retrieved last. Use a deterministic, reviewable resolver:

1. Select applicable requirements from deployment environment, data classification, application type and signed adoption records.
2. Apply mandatory enterprise requirements and approved domain-specific constraints; preserve both when compatible.
3. Apply application requirements, functional contracts and architectural decisions within that permitted scope.
4. Apply an exception only when its exact requirement/version, affected scope, approver authority, compensating controls and expiry are valid.
5. Treat recommendations and discovered patterns as suggestions. They cannot relax a mandatory requirement.

An unresolved conflict blocks the affected action and records who must decide. A stricter-looking rule is not automatically safe: it may break a supported business workflow. Require explicit decisions where security and functionality conflict. No natural-language model gets to authorize its own exception.

A standards release creates an upgrade proposal for each affected application. Compare requirement and test changes, inventory incompatible implementations, obtain appropriate owners' review, run conformance tests, then update the lock through a normal PR. Keep the previous lock for reproducibility. Urgent revocations or newly mandatory requirements trigger explicit reassessment according to organizational policy; they must not silently rewrite application commitments.

## 5. Executable obligations and the knowledge record

Associate each mandatory requirement with an applicability predicate, acceptance criteria and one or more check types: static query, unit test, functional test, configuration assertion, deployment observation or human review. Not every standard can be fully automated. Record `not_applicable`, `not_verified`, `failed`, `passed` and `approved_exception` distinctly, with an evidence basis for each.

Use a provider-neutral traceability chain:

`pack/version/requirement → change scenario → implementation revision → test ID → execution evidence → deployment observation`.

Codex, Claude or a future smaller model can propose the same artifacts and tests. CI executes trusted test commands in controlled environments. Keep the test implementation revision, fixture provenance, command, runner identity, timestamps, exit status and artifact digest. A task checkbox or an agent's “tests pass” statement is not an execution result.

[Custom schemas](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md) can add a `test-plan.md` before tasks. Post-implementation evidence can be retained separately or through an appropriately ordered custom artifact. Do not make evidence that requires implemented code a prerequisite for starting implementation. Schema dependencies establish artifact ordering/existence, not proof quality; enforce acceptance in CI.

For ten-year knowledge retention, preserve original specs, adopted versions, decisions, exceptions, changed source, tested repairs, failures and later regressions as linked records. Maintain valid-time and observation-time so historical questions can distinguish what was true from what was known. Rebuildable graph/vector indexes can change; source records and provenance remain recoverable. Apply retention, access and deletion policies rather than retaining raw sensitive logs indefinitely.

## 6. Example: repair claim authorization while preserving workflows

**Hypothetical application:** a claims API has a documented `GET /claims/{id}` endpoint. Ordinary assessors may read assigned claims in their tenant; tenant supervisors may read all claims in their tenant. Unauthenticated requests return 401; nonexistent and inaccessible claim IDs return the same 404 response. These are example contracts, not facts inferred about the user's system.

**Finding:** the handler looks up a claim by ID without consistently enforcing tenant and entitlement checks. `AUTHZ-017` requires resource authorization on every read. The repair must preserve valid assessor and supervisor access.

Create `openspec/changes/enforce-claim-authorization/`. The proposal cites the finding/evidence, adopted pack revision and existing capability `claim-access`. The design places checks in the existing shared authorization boundary, binds tenant identity to the validated principal and prevents client-supplied tenant values from widening access. Any documented service-account path must be included before implementation.

Example full replacement for the relevant requirement, under `specs/claim-access/spec.md`:

```markdown
## MODIFIED Requirements

### Requirement: Authorized claim retrieval
The API SHALL return claim details only to an authenticated assessor assigned
to that claim in the same tenant, or an authenticated supervisor of that tenant.

#### Scenario: Assigned assessor reads an existing claim
- **GIVEN** an assessor assigned to a claim in the assessor's tenant
- **WHEN** the assessor requests that claim
- **THEN** the API returns 200 with the existing response fields

#### Scenario: Tenant supervisor reads an unassigned claim
- **GIVEN** a supervisor and a claim in the same tenant
- **WHEN** the supervisor requests that claim
- **THEN** the API returns 200 with the existing response fields

#### Scenario: Cross-tenant access
- **GIVEN** an authenticated user from another tenant
- **WHEN** the user requests the claim
- **THEN** the API returns the documented 404 response without claim data

#### Scenario: Unassigned assessor
- **GIVEN** an assessor in the same tenant without assignment to the claim
- **WHEN** the assessor requests the claim
- **THEN** the API returns the documented 404 response without claim data

#### Scenario: Unauthenticated access
- **WHEN** a request lacks valid authentication
- **THEN** the API returns the documented 401 response without claim data
```

Before using this example, copy and preserve every relevant scenario from the real baseline; add cases for existing supported roles and workflows. The example is not a replacement for discovering those contracts.

The task/test plan should include unit tests for the entitlement matrix; functional tests using two tenants against the real route and test database; a security regression that fails on the vulnerable baseline and passes after the repair; and contract tests confirming successful response fields/status and documented errors remain compatible. Include missing-resource behavior and role/token edge cases relevant to the actual identity design.

The reviewer receives the spec delta, narrow code patch, tests, test results and impacted-boundary analysis. After deployment, a scoped authorized verification checks the actual released version. Only then does the knowledge base promote the result to a verified repair, with its applicable versions and preconditions. Later regressions reopen the record rather than erasing the earlier evidence.
