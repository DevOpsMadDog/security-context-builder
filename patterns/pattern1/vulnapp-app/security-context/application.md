# Pattern1 — Application security context (copy into vulnapp-app)

- App ID: vulnapp
- Environment: sandbox in ap-southeast-2
- Runtime: Node.js API, port 3000, /health endpoint
- Packaging: Docker image built by Azure Pipelines and published to ECR
- Deployment: AWS ECS Fargate service in private subnets
- Internet ingress: HTTPS ALB with AWS WAF; **never assume** it proves every route is protected
- Build identity: full Azure Repos app Git SHA + ECR digest + Azure Pipelines run ID

## Important flows and assets

- Client HTTPS request enters ALB and reaches API container by target group, port 3000.
- Application is not assigned a public IPv4 address.
- CloudWatch Logs receives application logs; avoid secrets and PII in log messages.
- If a database is added later, update the threat model and map its subnet, IAM and encryption controls before permitting agent remediation.

## Current security stance

This is a **hypothetical** application context, not a live AWS assertion. The example has no verified authentication/authorization scheme, secrets store, data classification or DAST coverage. Mark these as unknown until supported by real evidence.

## Owner and revision requirements

- Code owner: vulnapp-app application engineers.
- Scanner code targets must contain repository_id = vulnapp-app, correct relative path and exact app SHA.
- Dependency fixes must preserve the lockfile and be validated through unit, Playwright E2E and SAST/SCA rescans.
- No agent may infer the deployed image solely from branch name or an ECR mutable tag.
