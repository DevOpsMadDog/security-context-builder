#!/usr/bin/env python3
"""Assemble Pattern1's canonical evidence bundle; no vendor scanning occurs.

Inputs:
  * a deployment manifest from a trusted post-deploy collector
  * normalized scanner JSON from separately authenticated vendor adapters
  * exact current Azure Repos app / infra 40-character commit SHAs

Security: source descriptions remain untrusted. This script is NOT a native
Veracode SARIF, Inspector or Prisma adapter and does not authenticate payloads.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("context_compiler", ROOT / "context_compiler.py")
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
SHA = re.compile(r"^[a-f0-9]{40}$")


def read_json(path):
    p = Path(path)
    if p.stat().st_size > compiler.MAX_INPUT_BYTES:
        raise ValueError("input larger than compiler maximum")
    return json.loads(p.read_text(encoding="utf-8"), object_pairs_hook=compiler.reject_duplicate_keys)


def assert_scope(record, deployment, origin):
    for key in ("tenant_id", "app_id", "environment"):
        if record.get(key) != deployment[key]:
            raise ValueError(f"{origin}: scope differs at {key}")


def assemble(deployment, scans, app_sha, infra_sha):
    for label, sha in (("application", app_sha), ("infrastructure", infra_sha)):
        if not isinstance(sha, str) or not SHA.fullmatch(sha):
            raise ValueError(f"{label} SHA must be a full lower-case 40-hex commit")
    if not isinstance(deployment, dict) or not isinstance(scans, dict):
        raise ValueError("deployment and scans must be objects")
    if deployment.get("app_commit_sha") != app_sha or deployment.get("infra_commit_sha") != infra_sha:
        raise ValueError("deployment commit(s) do not match checked-out repositories")
    assert_scope(scans, deployment, "scanner bundle")
    if not isinstance(scans.get("sources"), list) or not scans["sources"]:
        raise ValueError("at least one normalized scanner source is required; missing scans are not clean results")

    repos = [
        {"id": "vulnapp-app", "kind": "application", "commit_sha": app_sha},
        {"id": "vuln-app-infra", "kind": "infrastructure", "commit_sha": infra_sha}
    ]
    observed = deployment["observed_at"]
    sources = [{
        "id": "deployment-observed",
        "kind": "deployment_manifest",
        "observed_at": observed,
        "max_age_hours": 24,
        "aws_account_id": deployment["aws_account_id"],
        "aws_region": deployment["aws_region"],
        "ecs_cluster_name": deployment["ecs_cluster_name"],
        "ecs_service_name": deployment["ecs_service_name"],
        "ecs_service_arn": deployment["ecs_service_arn"],
        "ecs_task_definition_arn": deployment["ecs_task_definition_arn"],
        "ecr_image_uri": deployment["ecr_image_uri"],
        "alb_arn": deployment["alb_arn"],
        "waf_web_acl_arn": deployment["waf_web_acl_arn"]
    }]
    resources = []
    seen_resource_ids = set()
    for item in deployment["resources"]:
        rid = item["id"]
        if rid in seen_resource_ids:
            raise ValueError("duplicate deployed resource id")
        seen_resource_ids.add(rid)
        owners = []
        if item.get("application_path"):
            owners.append({"role": "application", "repository_id": "vulnapp-app", "commit_sha": app_sha, "path": item["application_path"]})
        if item.get("infrastructure_path"):
            owners.append({"role": "infrastructure", "repository_id": "vuln-app-infra", "commit_sha": infra_sha, "path": item["infrastructure_path"]})
        resources.append({"id": rid, "mapping_source_id": "deployment-observed", "owners": owners})
    findings = []
    seen_finding_ids = set()
    for s in scans["sources"]:
        source_id = s["id"]
        role = s["repository_role"]
        if role not in ("application", "infrastructure", "cloud"):
            raise ValueError(f"{source_id}: invalid repository_role")
        source = {
            "id": source_id,
            "kind": s["kind"],
            "observed_at": s["observed_at"],
            "max_age_hours": s["max_age_hours"],
            "artifact_ref": s["artifact_ref"]
        }
        if role != "cloud":
            repo_id = "vulnapp-app" if role == "application" else "vuln-app-infra"
            expected = app_sha if role == "application" else infra_sha
            if s.get("commit_sha") != expected:
                raise ValueError(f"{source_id}: scanner source SHA does not match checked out {role} repo")
            source.update({"repository_id": repo_id, "commit_sha": expected})
        else:
            if str(s.get("aws_account_id")) != str(deployment["aws_account_id"]) or s.get("aws_region") != deployment["aws_region"]:
                raise ValueError(f"{source_id}: scan AWS account/region disagrees with deployment")
        sources.append(source)
        for finding in s["findings"]:
            fid = finding["id"]
            if fid in seen_finding_ids:
                raise ValueError(f"duplicate finding id: {fid}")
            seen_finding_ids.add(fid)
            if "path" in finding:
                if role == "cloud":
                    raise ValueError(f"{fid}: cloud scan cannot use a code-path target")
                target = {"repository_id": repo_id, "path": finding["path"]}
            elif "resource_id" in finding:
                target = {"resource_id": finding["resource_id"]}
                if target["resource_id"] not in seen_resource_ids:
                    raise ValueError(f"{fid}: unresolved deployed resource mapping")
            else:
                raise ValueError(f"{fid}: finding has no path or resource target")
            findings.append({
                "id": fid, "source_id": source_id, "title": finding["title"],
                "severity": finding["severity"], "state": finding["state"], "target": target
            })
    controls = [
        {"id": "waf-association-observed", "state": "passed", "evidence_source_ids": ["deployment-observed"]},
        {"id": "application-authz-unverified", "state": "unknown", "evidence_source_ids": []}
    ]
    bundle = {
        "bundle_version": 1,
        "tenant_id": deployment["tenant_id"], "app_id": deployment["app_id"],
        "environment": deployment["environment"],
        "repositories": repos, "sources": sources, "resources": resources,
        "findings": findings, "controls": controls, "fixes": []
    }
    cutoff = max(
        compiler.timestamp(s["observed_at"], f"{s['id']}.observed_at")
        for s in sources
    ).isoformat().replace("+00:00", "Z")
    # Validate with the existing reference compiler; do not "fix" a mismatch.
    compiler.validate(bundle, cutoff)
    return bundle


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--deployment", required=True)
    p.add_argument("--scans", required=True)
    p.add_argument("--app-sha", required=True)
    p.add_argument("--infra-sha", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    bundle = assemble(read_json(a.deployment), read_json(a.scans), a.app_sha, a.infra_sha)
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Canonical Pattern1 bundle written to {dest}: {len(bundle['findings'])} finding(s), evidence unverified")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        print(f"Pattern1 assembly failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
