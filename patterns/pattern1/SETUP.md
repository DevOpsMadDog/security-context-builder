# Pattern1 — Azure Pipelines setup checklist

This pattern does **not** create the Azure Repos repositories, AWS account, ADO service connections, scanner adapters or Terraform state. Its YAML samples become runnable only after the following environment-specific setup.

## Azure Repos

Create or select these two Azure Repos Git repos in the **same project**:

1. vulnapp-app — copy the contents of patterns/pattern1/vulnapp-app to its repository root.
2. vuln-app-infra — copy the contents of patterns/pattern1/vuln-app-infra to its repository root.

Create Azure Pipelines from the two YAML files in vuln-app-infra, with pipeline names **pattern1-deploy** and **pattern1-context**. Give the build identity read permission for vulnapp-app and access to all authorized resources.

Connect the GitHub repository DevOpsMadDog/security-context-builder with a GitHub service connection called **security-context-github**; authorize only the needed pipelines. Set **CONTEXT_BUILDER_SHA** to a reviewed full commit SHA which contains Pattern1 and the compiler; the context pipeline checks out this commit in detached mode.

Create Azure Pipelines Environment **security-sandbox** and require named human approvers and branch checks before its deployment job starts. ADO YAML does not itself set the approval policy.

## Secure variable groups

**pattern1-aws-sandbox** (grant only deployment pipeline access):

| Variable | Example/value type | Notes |
| --- | --- | --- |
| AWS_ACCESS_KEY_ID | secret | Prefer a federated or short-lived role instead |
| AWS_SECRET_ACCESS_KEY | secret | Never print |
| AWS_SESSION_TOKEN | secret or empty | Required for temporary STS credentials |
| ECR_REGISTRY | 111122223333.dkr.ecr.ap-southeast-2.amazonaws.com | Existing registry |
| ECR_REPOSITORY_NAME | vulnapp | Repository must exist before first build |
| ECR_REPOSITORY_URI | registry/vulnapp | Must match Terraform data source |
| VPC_ID | vpc-... | Existing sandbox VPC |
| PUBLIC_SUBNETS_HCL | ["subnet-public-a","subnet-public-b"] | Two distinct AZs |
| PRIVATE_SUBNETS_HCL | ["subnet-private-a","subnet-private-b"] | With endpoint/NAT reachability |
| ACM_CERT_ARN | arn:aws:acm:... | ACM cert in ALB region |
| TF_BACKEND_BUCKET | private Terraform-state bucket | Encryption, versioning, role restriction |
| TF_BACKEND_KEY | pattern1/sandbox/terraform.tfstate | Separate workspace/environment key |
| ECS_CLUSTER_NAME | vulnapp-sandbox | Must match Terraform |
| ECS_SERVICE_NAME | vulnapp-sandbox | Must match Terraform |

**pattern1-context** (grant only context pipeline access):

| Variable | Value |
| --- | --- |
| CONTEXT_BUILDER_SHA | approved 40-character GitHub commit SHA |

Set restricted retention/access on evidence artifacts. Native SARIF, Inspector and Prisma adapters must authenticate upstream data before publishing normalized-scans.json.

## Actual upstream artifacts for context pipeline

- **pattern1-deploy** publishes artifact **deployment-manifest/deployment.json** from post-apply AWS collection.
- **pattern1-normalized-security-scans** is a **separate** adapter pipeline you must implement using your licensed Veracode/Prisma/Inspector APIs and policies; it publishes artifact **normalized-scans/normalized-scans.json** matching fixtures/normalized-scans.example.json.
- **pattern1-context** consumes those two artifacts and checks out the app/infra revisions. In production, pin resource versions to the exact deployment and scan runs rather than silently using newest main. A mismatch must fail.

The synthetic fixture names/ARNS are examples only. Do not use the fixture as actual scan output or a basis to fix production systems.

## First run and gating

1. Pre-provision an isolated sandbox VPC, remote Terraform state bucket with versioning, S3 lockfile permissions and encryption, certificate and ECR repository.
2. Push the copied starter files to the two Azure Repos repositories.
3. Configure environment approvals, AWS permissions (scoped to sandbox), VPC subnet reachability and GitHub service connection.
4. Run pattern1-deploy manually for sandbox only; inspect Terraform plan and resulting deployment.json. The sample performs plan and apply inside a gated deployment job; for stricter change management split this into a plan artifact and separate approved apply that verifies plan provenance.
5. Have authenticated scanner adapters publish a normalized-scans.json aligned with deployed app SHA and AWS account.
6. Select *both* upstream pipeline run versions explicitly when launching pattern1-context, and choose the correct app/infra commit revisions.
7. Review generated manifest/finding packets; only then propose agent-driven PRs.

For actual enterprise use, the best AWS connection is short-lived role federation; adapt the sample key-pair environment variables to your approved identity integration. In this reference YAML, static AWS credentials are used solely to illustrate integration with an existing ADO variable group, **not** as a production recommendation.

## Validation and limits

- Terraform syntax, cloud-plan semantics, role permissions, WAF rule behaviour and Azure Pipelines runtime have **not** been tested against your actual Azure DevOps or AWS environment.
- Actual deployment may incur costs and creates an externally accessible ALB. It requires human review first.
- Code-level AppSec scans, Inspector, Prisma, Playwright, DAST, PR creation and Jira integration remain separate integration tasks.
- The only end-to-end executable offline component is normalization contract -> scoped compiler -> generated local security context.
