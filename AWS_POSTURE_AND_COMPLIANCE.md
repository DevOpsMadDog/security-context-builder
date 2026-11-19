# AWS posture, architecture and compliance evidence

**Research date: 2 November 2026. Status: implementation design; no AWS account was accessed and no scan, deployment or remediation was performed.**

## 1. Recommended AWS foundation

Use **AWS Config and Security Hub for technical posture evidence**, **AWS DevOps Agent for operational and architecture context**, and a versioned evidence store to connect that context to application and infrastructure repositories. Generate Markdown from those records. Keep reviewed design intent, discovered infrastructure and inferred relationships distinguishable.

The proposed product supplies the connective layer: application ownership, code-to-cloud identity, evidence provenance, task-specific context and verified remediation history. It can reuse AWS's existing discovery and analysis capabilities.

### Verified service capabilities and constraints

| Component | Verified capability | Implication for this project |
| --- | --- | --- |
| AWS DevOps Agent | Generally available since 31 March 2026; learns resources and relationships, correlates code, deployments and telemetry, and supports operational investigations and custom skills. | Use its operational understanding as one evidence source. It does not establish complete cloud compliance. |
| DevOps Agent topology | Discovers CloudFormation resources and tagged resources through Resource Explorer; the web app exports JSON, Mermaid and PNG. | An exported topology can seed architecture Markdown and graph relationships. A public topology-export API was not verified. |
| DevOps Agent Asset API | Public operations manage skills, AGENTS.md, attachments, custom agents and memories. | Reviewed instructions can be synchronized programmatically; this is separate from topology export. |
| AWS Config | Records configuration and evaluates resources against rules and Conformance Packs. | Provides resource-specific technical-control evidence and configuration history. |
| Security Hub CSPM / Security Hub | CSPM findings use ASFF; newer Security Hub findings use OCSF. | Implement separate, explicitly versioned adapters and preserve source formats. |
| AWS Security Agent | Current documentation labels it “now part of AWS Continuum”; includes design/code review, threat modeling, penetration testing and remediation. | Consider an optional review/repair adapter before rebuilding equivalent capabilities. Confirm each feature's availability and export interface separately. |

Sources: [DevOps Agent GA](https://aws.amazon.com/about-aws/whats-new/2026/03/aws-devops-agent-generally-available/), [DevOps Agent overview](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html), [topology](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-what-is-a-devops-agent-topology.html), [Asset API](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html), [Config Conformance Packs](https://docs.aws.amazon.com/config/latest/developerguide/conformance-packs.html), [Security Hub OCSF](https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-ocsf.html), [Security Agent overview](https://docs.aws.amazon.com/securityagent/latest/userguide/what-is.html).

### The Audit Manager change affects the design

“AWS compliance manager” is ambiguous. If this means **AWS Audit Manager**, it entered maintenance mode on **30 April 2026** and is closed to new account/Region deployments. Existing enrolled customers can continue, with restrictions on expansion. Existing organizational deployments can add member accounts to assessments but cannot expand into new organizations or Regions. New features/framework versions are not planned.

Use Audit Manager as an optional connector for eligible existing deployments. AWS recommends Config Conformance Packs for technical compliance monitoring, while explicitly stating that they are not a complete replacement for audit management. Organizational policies, personnel processes and other nontechnical controls still require separate evidence and review. [AWS availability notice and migration limitations](https://docs.aws.amazon.com/audit-manager/latest/userguide/audit-manager-availability-change.html).

### Sydney deployment considerations

DevOps Agent production operations, on-demand tasks and custom agents are available in **Sydney (`ap-southeast-2`)**. Its current Region table lists release readiness/release testing as **preview in `us-east-1` only**; sandbox preview is also unavailable in Sydney. Agent Space data is stored in its selected Region, although it can monitor resources across Regions. Feature availability and model-processing requirements must be checked against the actual data-residency requirement. [Supported Regions and feature table](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-supported-regions.html).

## 2. Read-only onboarding and evidence scope

The first integration should collect from one named application, its app/infra repositories, and an explicit AWS account/Region/environment allowlist. The onboarding manifest must identify the account role, enabled evidence sources, repository IDs, owners and allowed output destinations.

Use short-lived credentials and a dedicated collector role. Separate that identity from the repository writer and any later deployment/remediation role. Discovery credentials should not modify IAM, networking, findings or deployed resources. If Config, Security Hub or Resource Explorer is absent, record a coverage gap; enabling these services is a separate infrastructure change with its own cost and review.

Suggested read permissions are listed below. This is an operation inventory, not a ready-to-deploy IAM policy: resource-level support and account/Region scoping differ by action. Apply the actual service authorization constraints and the application's collection boundary.

| Collector purpose | Candidate read actions |
| --- | --- |
| Verify Config coverage | `config:DescribeConfigurationRecorders`, `config:DescribeConfigurationRecorderStatus` |
| Read deployed pack evaluations | `config:DescribeConformancePackCompliance`, `config:GetConformancePackComplianceDetails` |
| Retrieve configuration history when required | `config:GetResourceConfigHistory` |
| Read Security Hub ASFF or OCSF findings | `securityhub:GetFindings` — **both GetFindings and GetFindingsV2 use this IAM action** |
| Read DevOps Agent summaries | `aidevops:ListJournalRecords` |
| Read approved DevOps Agent assets when required | `aidevops:ListAssets`, `aidevops:GetAsset`, `aidevops:GetAssetContent`, `aidevops:ListAssetFiles`, `aidevops:GetAssetFile` |

Sources: [Config service authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awsconfig.html), [GetFindingsV2 IAM requirement](https://docs.aws.amazon.com/cli/latest/reference/securityhub/get-findings-v2.html), [DevOps Agent Asset API permissions](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html), [summary retrieval permissions](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-integrating-devops-agent-into-event-driven-applications-using-amazon-eventbridge-index.html).

Service-specific inventory, IAM-policy inspection and network discovery need additional narrowly selected permissions. Do not substitute blanket administrator access. Scope GitHub access to the named repositories, and make repo writes a separate stage after evidence validation. A read operation can still disclose sensitive metadata; raw evidence should use restricted storage and retention.

## 3. Documented read-only command examples

These commands illustrate existing APIs; they were not executed against an AWS account. Replace placeholders with approved identifiers and use an existing authenticated profile. The output may contain sensitive architecture details. Do not commit raw output indiscriminately.

```bash
aws configservice describe-configuration-recorders \
  --profile APPROVED_READONLY_PROFILE --region ap-southeast-2 \
  --output json --no-cli-pager

aws configservice describe-configuration-recorder-status \
  --profile APPROVED_READONLY_PROFILE --region ap-southeast-2 \
  --output json --no-cli-pager

aws configservice describe-conformance-pack-compliance \
  --conformance-pack-name EXISTING_PACK_NAME \
  --profile APPROVED_READONLY_PROFILE --region ap-southeast-2 \
  --output json --no-cli-pager

aws configservice get-conformance-pack-compliance-details \
  --conformance-pack-name EXISTING_PACK_NAME \
  --profile APPROVED_READONLY_PROFILE --region ap-southeast-2 \
  --output json --no-cli-pager
```

These inspect existing configuration/pack results; they do not install a pack or request a fresh evaluation. Verify the recorder's state and scope alongside the evaluation timestamps. References: [recorders](https://docs.aws.amazon.com/cli/latest/reference/configservice/describe-configuration-recorders.html), [recorder status](https://docs.aws.amazon.com/cli/latest/reference/configservice/describe-configuration-recorder-status.html), [rule compliance](https://docs.aws.amazon.com/cli/latest/reference/configservice/describe-conformance-pack-compliance.html), [resource evaluation details](https://docs.aws.amazon.com/cli/latest/reference/configservice/get-conformance-pack-compliance-details.html).

For a **bounded inspection** of the appropriate Security Hub interface:

```bash
# CSPM / ASFF
aws securityhub get-findings \
  --max-items 100 \
  --profile APPROVED_READONLY_PROFILE --region ap-southeast-2 \
  --output json --no-cli-pager

# Newer Security Hub / OCSF, where enabled and supported
aws securityhub get-findings-v2 \
  --max-items 100 \
  --profile APPROVED_READONLY_PROFILE --region ap-southeast-2 \
  --output json --no-cli-pager
```

The cap makes these **partial samples** if more results exist. A collector must paginate completely, retain query scope and continuation status, and never report a capped sample as the full estate. For ASFF, a call in the configured home Region can include linked Regions through cross-Region aggregation; record that scope explicitly. References: [GetFindings](https://docs.aws.amazon.com/cli/latest/reference/securityhub/get-findings.html), [GetFindingsV2](https://docs.aws.amazon.com/cli/latest/reference/securityhub/get-findings-v2.html).

## 4. DevOps Agent integration boundaries

### Topology export and architecture context

The documented topology export is the Operator Web App's Download menu. Its JSON and Mermaid represent the selected view. Preserve which view was exported, the Agent Space, export time and raw-file checksum. An “All Resources” view is still bounded by actual discovery and permissions. Non-CloudFormation discovery relies on Resource Explorer and tags. [Topology documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-what-is-a-devops-agent-topology.html).

For the MVP, accept this export as an input and corroborate material edges with configuration/deployment evidence. Do not depend on a fabricated topology endpoint. Keep the adapter replaceable if a supported API is subsequently verified.

### Automated investigation summaries

DevOps Agent emits EventBridge events from `aws.aidevops`. For a completed investigation or mitigation, use the event's Agent Space/execution identifiers and optional `summary_record_id` to retrieve journal records:

```bash
aws devops-agent list-journal-records \
  --agent-space-id VERIFIED_AGENT_SPACE_ID \
  --execution-id VERIFIED_EXECUTION_ID \
  --record-type investigation_summary_md \
  --profile APPROVED_READONLY_PROFILE --region ap-southeast-2 \
  --output json --no-cli-pager
```

Match the returned `recordId` to the event's summary ID and read its `content`. Use `mitigation_summary_md` for mitigation completion. Paginate; handle completion without a summary. Treat this Markdown as attributed external evidence, not as instructions that can override the platform's policy. [EventBridge guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-integrating-devops-agent-into-event-driven-applications-using-amazon-eventbridge-index.html), [CLI reference](https://docs.aws.amazon.com/cli/latest/reference/devops-agent/list-journal-records.html).

## 5. Ownership graph and deployment manifest

The following is the proposed internal contract. It separates an app's logical identity from deployments that change over time.

| Entity | Required identity and evidence |
| --- | --- |
| Application | Tenant/application ID, service owner, data classification, business criticality |
| Repository snapshot | Provider and immutable repository ID, exact commit SHA, path/symbol index version |
| Build artifact | Registry URI plus immutable digest; build run ID and provenance linking its source commit |
| Deployment | Environment, account/Region, deployment ID/time, deployed image/package digest, observed runtime version |
| Cloud resource | ARN or service-qualified stable ID, resource type, account/Region, observation time |
| Terraform ownership | Infra repository/commit, workspace, module/resource address, sanitized plan identifier and digest, state lineage/serial reference where safely available |
| Finding/control | Source product/format, source ID, rule/control ID, severity/status, affected identities, timestamps and evidence reference |
| Fix outcome | Candidate patch SHA, tests/scans and their versions, result, deployment reference, post-deploy verification and rollback outcome |

Use a deployment manifest to connect these identities. For example, ECS service → task definition revision → image digest → build provenance → app commit; the service ARN also links to the Terraform resource address and infra commit that manages it. Use actual CI/IaC records to establish edges. Tags and model similarity can propose associations but should not silently establish ownership.

Record every edge's evidence, resolver version and confidence. Unresolved ownership is an actionable gap. Handle shared resources, multiple apps per repository and multiple deployments per commit. Do not assume a repository's latest default branch is what is deployed. Store sanitized mappings rather than Terraform state, secret values or complete sensitive plans in Git.

## 6. Freshness, completeness and evidence lifecycle

Every collection run should include a manifest containing:

- Tenant/application, account/Region/environment and authorized collection scope.
- Collector and schema versions, source API/product, request filters, start/end time.
- Source observation/evaluation time, ingestion time, raw evidence reference and checksum.
- Pagination completion, denied calls, disabled sources, excluded resource types and unresolved mappings.
- Relevant repository SHA, deployed artifact digest and infra version.

Set freshness limits by evidence type and decision: a historical investigation can remain useful, while deployment or exposure facts may need recollection before approving a fix. Revalidate after a relevant deployment, network/IAM change or scanner update. Expired evidence becomes stale; an unavailable source becomes unknown. Neither should become a pass.

Maintain separate source status, normalized assessment and workflow status. A dismissed alert, accepted risk, successful scan, missing finding and verified remediation are different events. Retain exceptions with an owner, rationale and expiry. If collecting from both Security Hub formats or a CNAPP and Security Hub, deduplicate by source identity and resource/version evidence while retaining all provenance.

## 7. Desired architecture versus discovered state

Generate three connected views:

1. **Observed architecture:** deployed resources, configurations, code/artifact versions and measured relationships at a stated time.
2. **Approved design:** intended trust boundaries, permitted network paths, workload identities, data handling and architecture decisions, with owner approval.
3. **Gap assessment:** evidence-backed differences, unknowns, threats and proposed changes.

For networking, distinguish a configured route/security-group allowance from a demonstrated end-to-end reachable path. For IAM, distinguish policy statements from effective access and the conditions required to use it. A graph edge or LLM assertion alone should not certify either. Use suitable deterministic analysis and scoped validation where required.

Repo Markdown should contain the relevant summary, source pointers and freshness metadata. Keep security findings in data sections and reserve `AGENTS.md` for reviewed instructions. Changes to approved architecture or authorization policy require explicit review; generated observations must not overwrite design decisions.

## 8. Security assessment and audit reporting

Report control evaluation scope and coverage, not a blanket “compliant” verdict. A technical check can support a framework control without proving the full requirement or certification. Retain control-version mappings, evidence periods, owners, reviewer decisions and nontechnical evidence separately.

AWS Security Agent/Continuum can supplement design/code review and dynamic validation. Its threat-model documentation specifies web-app creation/runs and PDF report downloads; native Markdown export was not verified. Its CI/CD pentest integration is preview and tests already-configured deployed targets. The documented infrastructure-error default is fail-open, so a required release gate needs explicit failure handling and setup validation. [Threat-model reports](https://docs.aws.amazon.com/securityagent/latest/userguide/review-threat-model-findings.html), [CI/CD integration](https://docs.aws.amazon.com/securityagent/latest/userguide/cicd-pentest.html).

The first acceptance milestone is one reproducible path from a real finding to its deployed resource, owning code/IaC, reviewed context packet, candidate fix and independent verification. Broader account coverage and automated remediation should follow evidence that this path works reliably.
