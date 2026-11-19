# Pattern1 — Application remediation policy

This file is proposed agent context, **not a grant of authority**.

## Allowed proposal scope

- Propose a dependency or code patch to vulnapp-app only when code finding, scanner source and application Git SHA match.
- Generate unit tests and Playwright E2E tests to exercise both the fixed condition and unaffected user flows.
- Include the scanner finding ID, original dependency range, proposed package/lockfile update, and residual risk in the PR description.

## Required checks before merge

1. npm ci on a clean runner; build and unit tests must pass.
2. Playwright E2E must cover the critical flow and fail for a regression.
3. Veracode SAST/SCA re-run on the proposed commit, with a comparison of original and new finding IDs.
4. Container image rebuilt and scanned; use new immutable digest in sandbox.
5. If exposure warrants it, authorised DAST against sandbox, never a public target by default.
6. Reviewer explicitly approves and required branch policies pass.

## Fail closed / hand off

Do not auto-merge, deploy directly to production, downgrade an unresolved critical finding, or bypass failing tests. Do not treat a missing scan as success. For Terraform/IAM/network issues, create a linked infra change request instead of editing the app repo.
