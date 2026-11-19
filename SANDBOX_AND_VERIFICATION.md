# Sandbox and verification architecture

**Research date: 2 November 2026. Status: proposed implementation; no application sandbox, AWS deployment or penetration test was run.**

## 1. Build a repair system with an independent verifier

The custom agent should produce a candidate fix, regression tests and a verification plan. A separate execution service runs that plan inside an approved environment and returns attributable evidence. The agent can interpret failures and propose another patch, but cannot grant itself additional permissions, weaken the release gate or declare its own patch verified.

Use the organization's architecture, deployment manifests and security knowledge to construct the smallest environment that preserves the behavior being tested. A local sandbox can reproduce application workflows and selected AWS interfaces. It cannot automatically reproduce every production authorization, network, managed-service and organizational control.

The platform therefore needs an explicit **test-fidelity contract**: what was reproduced, what was substituted, what was exercised and which conclusions the environment can support. “End-to-end” always names a bounded journey and environment; it is not a claim that every enterprise integration was tested.

## 2. Use five verification layers

| Layer | Environment and checks | What a pass establishes | What remains unproven |
| --- | --- | --- | --- |
| 0: source and unit | Isolated checkout; compilation, lint, SAST/SCA, unit/property tests, dependency and IaC checks | Candidate satisfies the checked source-level and unit-level assertions | Deployed behavior, real cloud authorization and network enforcement |
| 1: local integration | Disposable runtime; actual app, database, cache, queue or browser containers | Tested application interactions work with the declared dependency versions | Managed-service and organization-control equivalence |
| 2: AWS emulation | Pinned LocalStack or focused Moto mocks with an explicit supported-feature matrix | Declared scenarios work under those emulated API semantics | Untested or unsupported IAM, network and AWS service behavior |
| 3: real AWS sandbox | Leased isolated account(s), vetted infrastructure and representative policies | Tested cloud interactions and controls hold in the stated sandbox configuration | Production data, scale and configuration differences |
| 4: deployment validation | Approved preproduction/canary deployment, observability and originating control recheck | Deployed artifact passes the scoped post-deployment checks | Universal absence of vulnerabilities or future drift |

This is a proposed gating structure. Select required layers from the change's behavior and risk. A local parser fix may need layers 0–1. An IAM boundary, KMS policy, VPC endpoint or EKS identity change normally needs representative real-AWS validation. Do not run every expensive layer for every change; do not let a cheap layer stand in for an essential control.

### Testcontainers and Moto

Testcontainers supplies throwaway instances of real containerized dependencies, including databases, browsers and arbitrary containers. Use it to preserve actual SQL behavior, migrations, transactions and dependency protocols. It orchestrates tests; it is not a tenant-security boundary. [Official Testcontainers overview](https://java.testcontainers.org/).

Moto is useful for focused AWS-client unit tests and fault/response scenarios. Its documentation requires mocks to be established before boto3 clients; otherwise a client can escape the intended mock. Use dummy credentials, no inherited AWS profile and denied external AWS egress as additional controls. Pin the version and check implemented endpoints; passing a mock is evidence about the mock scenario. [Moto setup](https://docs.getmoto.org/en/latest/docs/getting_started.html), [implemented services](https://docs.getmoto.org/en/latest/docs/services/index.html).

## 3. LocalStack: useful, with explicit limits

LocalStack's current plans distinguish commercial **Base, Ultimate and Enterprise** from noncommercial **Hobby**. The documentation directs primarily automated/shared-platform use cases to discuss the applicable commercial arrangement. Its plan table describes service entitlement, explicitly not complete API/feature coverage. Record the chosen plan, version/image digest and enabled capabilities in each environment manifest. Do not assume a community or Hobby license covers an enterprise repair service. [Plans and licensing](https://docs.localstack.cloud/aws/licensing/).

**IAM enforcement is disabled by default.** Supported paid capabilities require explicitly enabling `ENFORCE_IAM=1` for authorization testing. The current engine evaluates identity/resource policies, permission boundaries and SCPs, but coverage remains feature-specific. The coverage page lists unsupported principal forms, policy variables and a CloudFormation stack-permission limitation. Test both intended allow and deny cases for the exact services, conditions and call chains used. [IAM enforcement](https://docs.localstack.cloud/aws/developer-tools/security-testing/iam-policy-enforcement/), [IAM coverage](https://docs.localstack.cloud/aws/developer-tools/security-testing/iam-coverage/).

Network fidelity also needs inspection. LocalStack's EC2 Docker manager runs containers, documents container-related networking limitations and currently documents support for the default security group in its walkthrough. It requires the Docker socket and exposes that socket to launched EC2 containers. Those mechanics are unsuitable as a boundary between untrusted jobs on a shared host. Put that daemon and emulator inside a disposable per-job VM; do not mount a shared enterprise host's Docker socket into agent-generated code. [EC2 implementation and limitations](https://docs.localstack.cloud/aws/services/ec2/).

A successful `CreateVpc`, `PutKeyPolicy` or policy simulation is not evidence that the corresponding production control was exercised. Route scenarios to real AWS when the claimed security outcome depends on unsupported or materially different behavior.

## 4. Define the environment contract before execution

Each scenario manifest should describe:

- Application/infra repository IDs and exact base/candidate commits; built image digests and dependency locks.
- Business journey, security invariant, affected trust boundaries and expected allowed/denied outcomes.
- Required databases/services/versions, account relationships, identities, roles and network paths.
- Real components, emulated components and stubs; coverage gaps and known semantic differences.
- Synthetic data, user personas, reset procedure, test clock/seed and external-service substitutes.
- Required verification layers, time/resource limits, egress allowlist and authorization scope.
- Verifier/test-suite version, evidence destinations, retention and teardown requirements.

Generate this contract from reviewed architecture and dependency facts, then validate it against a controlled schema. A model may propose missing dependencies; it must not silently invent or approve them. Bind results to the contract hash. A changed manifest or patch invalidates prior results relevant to that change.

An organization simulation should preserve meaningful boundaries: two application tenants, normal/admin/support identities, workload-to-resource permissions, shared services, asynchronous jobs and sensitive-data flows. Replace customer data with synthetic fixtures. Stubbing an external identity provider is acceptable for a local contract test, but final federation validation needs an approved test identity tenant or real sandbox configuration.

## 5. Require original failure, patched success and preserved functionality

For a reproducible security defect, run the same security regression against the original and patched versions under equivalent conditions:

1. Establish a healthy baseline. Existing business journeys must run, or their failures must be recorded before attributing them to the patch.
2. Reproduce the defect on the exact original commit. The security assertion should fail for the intended reason; a timeout, missing fixture or broken environment is not a valid reproduction.
3. Apply the candidate patch and run the unchanged security assertion. It should pass because the vulnerability condition is removed.
4. Run permitted business journeys, denied journeys, edge cases and the affected regression suite.
5. Re-run the originating scanner/control where applicable, then verify the deployed artifact at the required fidelity layer.

For an authorization repair, test that one tenant cannot read or modify another tenant's object **and** that its owner and authorized support workflow still work. Check database side effects, queued work and audit events, not only the HTTP status. For an SSRF repair, test forbidden destinations and redirects alongside legitimate outbound integrations. For dependency changes, verify application behavior and the actual resolved dependency/artifact.

If the original defect cannot be reproduced, label the result accordingly and apply the relevant review policy. Do not manufacture a red test merely to create a success story. For probabilistic/time-dependent failures, preserve seeds, schedules and observed frequency; a rerun-until-green strategy is not verification.

## 6. Keep test authority separate from patch generation

Agent-generated tests are useful candidate artifacts. They are not sufficient as the sole acceptance authority. Maintain a trusted baseline suite, organization-owned security contracts and independently generated or reviewed adversarial cases in a verifier-controlled location.

The verifier must reject unauthorized changes to assertions, expected responses, fixture privilege, scanner configuration, exclusions and mandatory test discovery. Record skips and expected failures explicitly. Run source-control diff checks for weakening changes; verify that required suites actually executed and returned usable results. Code coverage is supporting information, not proof of a fix.

Use separate credentials and filesystem access for the patch agent, test runner, evidence publisher and deployment orchestrator. The patch job cannot edit the trusted harness or release policy. Independent review can include another agent, but acceptance depends on executable assertions, tool results and required human decisions rather than an LLM's confidence score.

Model budgets and iteration limits should cap repair attempts. On exhaustion, retain the best evidence and a clear unresolved state; do not silently lower the gate.

## 7. Sandbox isolation and CI authorization

Use separate worktrees/checkouts to avoid file collisions, but recognize that a worktree alone provides no execution isolation. For untrusted or agent-modified code, place each job in a disposable VM or similarly strong isolated runtime; containers and Testcontainers run inside that boundary. Use per-job networks, storage, caches and identities. Avoid reusable environments across tenants.

Start without production credentials, cloud instance metadata access, host home directories or shared Docker sockets. Provide only synthetic/local secrets at lower layers. Limit CPU, memory, process count, disk and wall time. Deny egress by default; allow required package registries and test endpoints through controlled access. Dependency installation and build scripts execute code and need the same boundary as tests.

For CI, separate untrusted build/test execution from privileged artifact publication and deployment. Pin trusted workflow dependencies, scope tokens to required repositories/actions and require explicit permission for the cloud stage. Do not check out and execute untrusted PR content inside a privileged `pull_request_target` job. GitHub documents that persistent self-hosted runners can be compromised by untrusted code and describes ephemeral/JIT runner approaches. [GitHub secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use).

A privileged orchestrator should accept typed requests referencing approved artifacts, account leases and scenario IDs. It must enforce the allowed operation set independently of prompts. Short-lived OIDC/STS credentials belong only in the authorized stage and must be scoped to the actual repository/environment and target sandbox resources.

## 8. Real AWS validation and IaC execution

Prefer a pool of dedicated sandbox accounts in a controlled OU, leased per job or tenant. A VPC alone does not isolate account-wide IAM and organization policy effects. Cross-account access scenarios may need two accounts. Establish representative SCPs, boundaries, resource policies, KMS policies, endpoint policies and identity federation without connecting production data or production trust paths.

Validate the target account/Region, lease and infrastructure plan before apply. The orchestrator provisions vetted modules or a reviewed candidate plan with bounded resources. Test relevant behavior on real services: KMS grants/decryption context, IAM/STS identity, VPC routing/DNS/endpoints, WAF rules or EKS workload identity when affected. Record differences from production and avoid claiming complete parity.

`terraform plan` proposes changes; it does not execute them. Terraform's mocked providers generate fake computed data. Consequently, a passing plan or mock-based Terraform test supports configuration assertions, while deployment behavior requires apply and functional checks. Terraform test configurations can use real providers, so route them according to their actual effect. Treat saved plans/state as sensitive evidence. [Terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan), [provider mocking](https://developer.hashicorp.com/terraform/language/tests/mocking).

AWS's Innovation Sandbox solution provides an existing account lease/lifecycle pattern, including cleanup and quarantine when cleanup fails. Reuse or adapt that account-management approach instead of letting repair agents create unrestricted accounts. [AWS sandbox account lifecycle](https://docs.aws.amazon.com/solutions/latest/innovation-sandbox-on-aws/account-lifecycle-in-isb.html).

## 9. Cost, termination and cleanup are verification outcomes

Every lease needs an expiry, owner, job ID, allowed Regions/resource classes, concurrency limit and estimated budget. Use quotas, restricted instance sizes, resource allowlists and an external watchdog alongside budget alerts. AWS documents that billing/notification delays can allow spend beyond a budget threshold; an alert is not a hard instantaneous cap. [AWS Budgets limitations](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).

Run teardown from a controller that survives runner failure. Revoke job credentials, destroy managed resources and inspect for residual storage, snapshots, endpoints and other chargeable resources. Preserve required sanitized evidence before deletion. A failed destroy must leave a tracked cleanup failure and quarantine the account from reuse; it must not be reported as a clean run. Retain teardown inventory and cost attribution for audit and operations.

## 10. Feed verified outcomes into the enterprise AppSec KB

Record immutable links between finding, source/deployment snapshot, security requirement, patch, environment contract, test suite, raw results and release decision. Include failures and unsuccessful approaches. Distinguish `candidate`, `locally_verified`, `cloud_verified`, `deployed_verified`, `rejected`, `inconclusive` and `accepted_exception`; these states can coexist with separate workflow and cleanup status.

A reusable fix recipe needs preconditions, supported languages/framework versions, the security invariant, allowed transformations, counterexamples and required verification. Promote it only after review of real outcomes. Similarity retrieval can suggest a recipe; deterministic checks must establish that its preconditions hold. Invalidate or re-evaluate recipes when dependencies, control requirements or architecture change.

Enforce tenant/repository access before retrieval, retain provenance and remove secrets from logs and training material. Do not automatically train a smaller model on unverified patches or passing emulator-only runs. The knowledge asset is the tested relationship between a problem, its context, a change and its measured outcome. That evidence lets future models become smaller without weakening the verification boundary.
