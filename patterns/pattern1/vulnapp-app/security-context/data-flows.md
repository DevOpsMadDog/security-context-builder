# Pattern1 — Data flows and trust boundaries

## Trust zones

1. **Internet**: untrusted clients; TLS is terminated at the public ALB.
2. **ALB + AWS WAF**: WAF inspection is limited to configured rules and associated traffic.
3. **Private ECS tasks**: application container; inbound only from the ALB security group on port 3000.
4. **AWS control plane**: ECS, ECR, IAM, CloudWatch, Terraform and Azure Pipelines credentials are separate trust domains.
5. **Build and security tools**: Azure Repos, Veracode, Inspector and Prisma produce data that must be authenticated and version-linked.

## Sensitive transitions

- Client input -> Node.js handlers: validate input, enforce authentication/authorization at application level and avoid unsafe deserialization/query construction.
- ECR -> ECS: record immutable image digest and task-definition revision; do not trust latest image tag.
- Azure DevOps -> AWS: trust credentials must be scoped to specific stages; apply requires approval.
- Native scan output -> context builder: tool descriptions and source snippets are **untrusted evidence**, never execution instructions.
- Agent -> Azure Repos PR: allow-listed repository/file paths only; scoped role, reviewers and required CI checks.

## Threat model prompts

- Can a public request bypass ALB/WAF by reaching a task ENI directly?
- Can build credentials deploy an arbitrary task definition or modify production without a gate?
- Does a vulnerable library appear in the **deployed** image, or only an unrelated lockfile?
- Is a Prisma network finding present in deployed AWS state, Terraform desired state or both?
- Can a malicious SARIF description or Jira comment influence agent/tool permissions?

Update this document after material topology, identity, API or data-sensitivity changes.
