#!/usr/bin/env python3
"""Collect *observed* Terraform/AWS ECS provenance for Pattern1 after sandbox apply.

Requires terraform, aws CLI, a configured AWS identity. Fail closed: the output
must not be treated as a signed or independently authenticated attestation.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

FULL_SHA = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def command(*args, cwd=None):
    return json.loads(subprocess.check_output(args, cwd=cwd, text=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--terraform-dir", required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--app", required=True)
    ap.add_argument("--environment", required=True)
    ap.add_argument("--app-sha", required=True)
    ap.add_argument("--infra-sha", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    for label, sha in [("app", args.app_sha), ("infra", args.infra_sha)]:
        if not FULL_SHA.fullmatch(sha):
            ap.error(f"{label} SHA must be 40 lowercase hex characters")

    tf = command("terraform", "output", "-json", cwd=args.terraform_dir)
    def val(key):
        if key not in tf or "value" not in tf[key]:
            raise ValueError(f"missing Terraform output: {key}")
        return tf[key]["value"]

    cluster, svcname = val("ecs_cluster_name"), val("ecs_service_name")
    aws_id = command("aws", "sts", "get-caller-identity")["Account"]
    if str(aws_id) != str(val("aws_account_id")):
        raise ValueError("AWS identity differs from Terraform state account")
    resp = command("aws", "ecs", "describe-services", "--cluster", cluster, "--services", svcname)
    if resp.get("failures") or len(resp.get("services", [])) != 1:
        raise ValueError("ECS service missing or ambiguous")
    svc = resp["services"][0]
    if svc.get("status") != "ACTIVE" or svc.get("runningCount", 0) < 1:
        raise ValueError("ECS service not healthy/running")
    if svc.get("taskDefinition") != val("ecs_task_definition_arn"):
        raise ValueError("ECS active task definition disagrees with Terraform")
    task = command("aws", "ecs", "describe-task-definition", "--task-definition", svc["taskDefinition"])["taskDefinition"]
    api = next((x for x in task["containerDefinitions"] if x["name"] == "api"), None)
    if not api or not DIGEST.search(api.get("image", "")):
        raise ValueError("task definition image is not digest pinned")
    lb = command("aws", "elbv2", "describe-load-balancers", "--load-balancer-arns", val("alb_arn"))["LoadBalancers"]
    if len(lb) != 1:
        raise ValueError("ALB mapping is ambiguous")
    acl = command("aws", "wafv2", "get-web-acl-for-resource", "--resource-arn", val("alb_arn"))
    if acl.get("WebACL", {}).get("ARN") != val("waf_web_acl_arn"):
        raise ValueError("actual WAF association is absent or different from Terraform")

    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {
        "tenant_id": args.tenant,
        "app_id": args.app,
        "environment": args.environment,
        "observed_at": observed_at,
        "app_commit_sha": args.app_sha,
        "infra_commit_sha": args.infra_sha,
        "aws_account_id": str(aws_id),
        "aws_region": val("aws_region"),
        "ecs_cluster_name": cluster,
        "ecs_service_name": svcname,
        "ecs_service_arn": svc["serviceArn"],
        "ecs_task_definition_arn": svc["taskDefinition"],
        "ecr_image_uri": api["image"],
        "alb_arn": val("alb_arn"),
        "waf_web_acl_arn": val("waf_web_acl_arn"),
        "resources": [{
            "id": "ecs-vulnapp-service",
            "application_path": "src/server.js",
            "infrastructure_path": "terraform/main.tf"
        }, {
            "id": "internet-alb",
            "infrastructure_path": "terraform/main.tf"
        }]
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Observed deployment manifest: {out} (contains topology; restrict artifact access)")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
