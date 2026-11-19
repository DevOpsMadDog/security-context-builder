# Pattern1 — Infrastructure and deployment security context (copy into vuln-app-infra)

**Expected topology:** internet -> regional AWS WAF associated with HTTPS ALB -> target group (IP) -> ECS Fargate service, desired count two, task port 3000, private subnets, CloudWatch Logs.

## Terraform ownership

- Repository: vuln-app-infra
- Infrastructure path: terraform/main.tf
- Resources: aws_lb.app, aws_lb_listener.https, aws_lb_target_group.app, aws_wafv2_web_acl.app, aws_wafv2_web_acl_association.app, aws_ecs_cluster.app, aws_ecs_service.app, aws_ecs_task_definition.app, aws_ecr_repository.app, IAM execution and task roles, security groups.
- Input constraints: existing VPC, public/private subnets, ACM certificate, private egress path and encrypted remote Terraform state.
- Terraform output inventory: region, cluster name, ECS service name/ARN, task definition ARN, ALB ARN, WAF ARN and ECR URL.

## Evidence to collect **after apply**

- Azure DevOps run ID, app and infra Git SHAs, Terraform plan checksum and deployment approval.
- AWS account ID, region and ECS cluster/service identity.
- ECS service status, running/pending/desired task counts, active task-definition ARN, task image reference and resolved ECR digest.
- Actual ALB listener, target group health, WAF association, SG ingress/egress and task public IP assignment.
- Resource-to-Terraform path mapping and confirmed scanner target ARNs.

## Policy boundaries

- Never run terraform apply using credentials exposed to external/untrusted PRs.
- Do not assume Terraform desired configuration equals active AWS configuration.
- An agent with only a Prisma finding may propose a **reviewed** infra PR; it must not mutate live WAF, IAM or SG via AWS API.
- Treat stale, missing or conflicting mapping as unknown: first reconcile drift and provenance.
- Rollback is an explicit reviewed change or deployment to a prior approved task definition, not an unverified automatic revert.
