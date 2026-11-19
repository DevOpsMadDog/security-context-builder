# Pattern1 — Azure DevOps application + Terraform infrastructure on AWS ECS Fargate

Status: **reference architecture and synthetic evidence demonstration; not deployed**. This pattern is deliberately isolated from production. It shows how the central Security Context Builder can provide grounded, commit-scoped context to AppSec agents when an application and its AWS infrastructure are maintained in **two Azure DevOps repositories**.

## 1. The three code locations

Only **two repos are in Azure DevOps**. The third is the shared GitHub context-tooling repo; it is a read-only build dependency and not another application repository.

| Repository | System | Ownership | Example contents |
| --- | --- | --- | --- |
| vulnapp-app | Azure Repos | Application team | Node.js API, Dockerfile, package-lock, unit/Playwright tests, security-context/ |
| vuln-app-infra | Azure Repos | Platform team | terraform/, azure-pipelines.deploy.yml, azure-pipelines.context.yml, security-context/ |
| DevOpsMadDog/security-context-builder | GitHub | Security platform team | context_compiler.py, standard schemas, patterns/pattern1/ |

Copy the two directories beneath this pattern to the roots of their **corresponding Azure Repos repositories**; do not check out the GitHub repo as an extra source-of-truth for app or infra.

Suggested target layout:

~~~text
vulnapp-app/                                  (Azure Repos)
  src/server.js
  package.json / package-lock.json
  Dockerfile
  tests/
  security-context/
    application.md
    data-flows.md
    remediation-policy.md

vuln-app-infra/                               (Azure Repos)
  terraform/main.tf
  azure-pipelines.deploy.yml
  azure-pipelines.context.yml
  security-context/aws-deployment.md

security-context-builder/                     (GitHub; read-only CI dependency)
  context_compiler.py
  patterns/pattern1/
    fixtures/bundle.example.json
    fixtures/deployment.example.json
    fixtures/normalized-scans.example.json
    scripts/build_bundle.py
~~~

## 2. What is deployed

~~~mermaid
flowchart LR
  U[Browser or API consumer] --> W[AWS WAF web ACL]
  W --> ALB[Internet-facing HTTPS ALB]
  ALB --> TG[Target group: IP]
  TG --> ECS[ECS service on Fargate, two tasks]
  ECS --> CW[CloudWatch Logs]
  ADO1[Azure Repo: vulnapp-app] -->|Docker image build| ECR[Amazon ECR]
  ECR --> ECS
  ADO2[Azure Repo: vuln-app-infra] -->|Terraform plan and apply| AWS[AWS VPC, SG, ALB, WAF, ECS, IAM]
  AWS --> ALB
  AWS --> ECS
  S[Veracode SAST/SCA + Inspector + Prisma] --> N[Trusted adapters / normalized evidence]
  ADO1 --> C[Context compiler]
  ADO2 --> C
  N --> C
  AWS -->|AWS inventory + Terraform outputs + run provenance| C
  C --> P[Per-finding packets + app/infra Markdown + manifest + SQLite]
  P --> R[Review-first agent / fix PR in owning repo]
  R --> V[Build, unit, Playwright, SAST/SCA rescan, IaC checks, sandbox, optional DAST]
~~~

The Terraform example assumes an **existing VPC**, two public subnets in different AZs, private task subnets with ECR/CloudWatch connectivity, an ACM certificate, and remote state. It provisions the ALB, WAF, target group, ECS service/task definition, security groups, ECR, IAM roles and log group. Do **not** deploy the demo publicly with deliberately vulnerable application code.

## 3. Traceability / canonical identity

This is the key design constraint: a scanner finding is **not** sufficient to authorize a fix.

| Link | How to derive it | Why the agent needs it |
| --- | --- | --- |
| App repo SHA | git rev-parse HEAD from authorized Azure Repos checkout | Code finding only applies to this revision |
| Infra repo SHA | git rev-parse HEAD from Terraform checkout | Terraform findings point to the matching IaC revision |
| Image provenance | ECR image digest from build and deployed task definition | Map deployment to **immutable** application artifact |
| Infrastructure ownership | Terraform output, state/resource address and explicit repo/path mapping | Determine whether an infra PR is needed |
| Deployed topology | AWS ECS/ELB/WAF read APIs plus account and region | Validate actual exposure, routing and security controls |
| Scanner provenance | Veracode SAST/SCA SARIF, AWS Inspector, Prisma | Identify finding origin, time, target and confidence |
| Approval/evidence | Pipeline run URL, change ticket, reviewed PR SHA, test results | Reproducible decision trail |

**Do not assume** an ECS service uses the latest image merely because a build pushed to ECR. The evidence producer must record the task-definition revision, image digest, and relevant app/infra pipeline IDs. The current compiler schema validates scoped commit relationships but does **not** independently attest to ECR digests, Terraform state or provider scan authenticity.

## 4. The workflow in twelve steps

1. Scrum master opens a Jira ticket, e.g. APPSEC-101, from Veracode, Inspector or Prisma. Ticket is a trigger/reference, not a source of security truth.
2. App CI checks out vulnapp-app at its resolved Git SHA; Terraform CI checks out vuln-app-infra at its resolved Git SHA.
3. Azure Pipelines builds and tests the Node.js app, publishes its ECR image by commit tag, and records the resulting immutable image digest.
4. The gated deployment pipeline runs terraform init, validate, plan, reviewed approval, and apply to the approved sandbox environment. Terraform remote state must use locking and least privilege.
5. The pipeline verifies ECS service stability and obtains task definition, target group, ALB, WAF, AWS account/region plus Terraform outputs. It emits a deployment manifest with the exact app and infra Git SHAs.
6. Enterprise adapters ingest Veracode SARIF/SCA, Inspector and Prisma **as external evidence**. They normalize product-specific formats to a reviewed mapping contract; no missing scanner is silently treated as zero findings.
7. The normalization/assembly script builds one canonical JSON bundle for tenant + application + environment using the deployment record, normalized scanner evidence, exact Git SHAs and source TTLs.
8. The pinned context_compiler.py checks owner paths, source SHA alignment, freshness and scope; it writes application.md, infrastructure.md, finding packets, manifest.json and ledger.sqlite.
9. Agents consume **only the relevant context/finding packets** plus approved standards. Output is a proposed code/infra patch and evidence-linked explanation, not unattended execution.
10. Application fixes go to a vulnapp-app PR (for example a dependency or request validation fix); infrastructure fixes go to a vuln-app-infra PR (for example an IAM, ingress, image runtime or WAF rule fix). A split finding may require two coordinated PRs.
11. PR validation reruns build + unit + Playwright E2E + SAST/SCA and, for infrastructure changes, Terraform formatting/validation/plan and Checkov. A sandbox deployment, Inspector/Prisma re-evaluation and authorised DAST may be required based on risk.
12. A human reviews the PR and verification results, then the approved deployment updates both provenance and fresh security context. Retain signed, access-controlled evidence outside source control.

See **[SETUP.md](SETUP.md)** for the exact Azure Pipelines variable groups, authorisations, AWS prerequisites and upstream artifact requirements.

## 5. What to copy and run

**Offline contract validation (no AWS/ADO/Veracode credentials required):**

~~~bash
python3 context_compiler.py compile \
  --input patterns/pattern1/fixtures/bundle.example.json \
  --out /tmp/pattern1-evidence \
  --as-of 2026-11-19T12:15:00Z

python3 -m unittest discover -s tests -v
python3 -m unittest discover -s patterns/pattern1/tests -v
~~~

**Assemble a canonical bundle from normalized inputs** (also offline; fixture only):

~~~bash
python3 patterns/pattern1/scripts/build_bundle.py \
  --deployment patterns/pattern1/fixtures/deployment.example.json \
  --scans patterns/pattern1/fixtures/normalized-scans.example.json \
  --app-sha aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --infra-sha bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --out /tmp/pattern1-bundle.json

python3 context_compiler.py compile \
  --input /tmp/pattern1-bundle.json \
  --out /tmp/pattern1-evidence \
  --as-of 2026-11-19T12:15:00Z
~~~

The example data uses reserved demo identifiers and **invented findings**. It is not output from Veracode, Inspector, Prisma, ECS or Terraform.

**Azure Pipelines:** Copy the two example YAML files into vuln-app-infra. Set the project/repository references, authorised GitHub service connection, protected AWS credentials (or federated role), existing remote Terraform state, ECR, VPC/subnets, ACM certificate and approved environment. The context pipeline expects **real, independently produced** deployment and normalized scan artifacts. It fails rather than inventing missing evidence.

## 6. PR routing and security decisions

| Finding | Root cause evidence | Owning change | Verification |
| --- | --- | --- | --- |
| Veracode SCA — vulnerable direct dependency (synthetic) | SARIF/SCA with app SHA + package manifest | vulnapp-app PR | npm lockfile update, unit, Playwright, rescan |
| Prisma — overly broad egress (synthetic) | Cloud posture + SG ARN/terraform state/resource map | vuln-app-infra PR | Terraform plan, Checkov, sandbox, cloud posture rescan |
| Inspector — deployed image vulnerability (synthetic) | Task definition + ECR digest + Inspector finding | vulnapp-app (possibly infra coordinated) PR | rebuild immutable image, redeploy sandbox, Inspector re-evaluation |
| Unclear resource ownership or stale scan | Missing deployment link or expired evidence | No automated PR | Refresh evidence and request human mapping |

An agent must not apply fixes from a stale or guessed ownership map. Never feed scanner descriptions as trusted instructions. No live exploitation, scanning, cloud changes, automatic Jira posting or PR creation is implemented by the compiler.

## 7. Production hardening gaps

- Prefer short-lived AWS federation and least-privilege role assumption over long-lived admin access keys in variable groups. Azure DevOps secret variable groups still require explicit pipeline authorisation.
- Require manual approvals for Terraform apply; do not run apply from untrusted PRs with cloud write credentials.
- Pin third-party tooling/CLI versions and protect GitHub checkout to an reviewed commit SHA; example pipelines include a checkout SHA verification step.
- Store raw scans, account topology, Terraform state and environment evidence in restricted ADO artifacts/S3, not a public GitHub repository.
- Record data-source observations and TTL using collector timestamps; never reset an old scan's freshness timestamp merely by reprocessing it.
- Verify WAF association and task-definition/image digest on AWS, not simply Terraform desired state. Pin multi-repo checkouts to a coordinated release/deployment.
- The offline compiler is a small, trusted-input reference tool. It is **not** a SARIF/ASFF/Prisma parser, a PR generator or a production security policy engine.

## References

- Azure Pipelines multi-repository checkout: https://learn.microsoft.com/en-us/azure/devops/pipelines/repos/multi-repo-checkout
- Azure DevOps variable groups: https://learn.microsoft.com/en-us/azure/devops/pipelines/library/variable-groups
- AWS ECS services and ALB: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs_services.html
- AWS CLI ECS deployment inventory: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_AWSCLI_Fargate.html
