#!/usr/bin/env python3
"""Offline security-context proof of concept (Python 3.10+, standard library only).

Compile a canonical, single-scope evidence bundle:
  python context_compiler.py compile --input examples/demo-bundle.json \
      --out ./output --as-of 2026-11-02T02:00:00Z
Query evidence-backed, reported verified fixes using exact tenant/app/environment:
  python context_compiler.py query --db OUTPUT_LEDGER_PATH \
      --tenant demo --app claims --environment staging --text encryption

No AWS, scanner, graph extractor, model, deployment, or verification API is called.
The demo is synthetic. SQLite substring search is deliberately not vector search.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone


GENERATOR = "security-context-compiler/1"
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
SHA = re.compile(r"^[a-fA-F0-9]{40}$")
ROLES = {"application", "infrastructure"}
MAX_INPUT_BYTES = 8 * 1024 * 1024


class ValidationError(ValueError):
    """The bundle or output destination cannot be safely processed."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def text_field(value, name, limit=4096):
    require(isinstance(value, str) and 0 < len(value) <= limit, f"{name}: expected nonempty text <= {limit} characters")
    require(not any(ord(c) < 32 and c not in "\n\t" for c in value), f"{name}: control characters are forbidden")
    return value


def identifier(value, name):
    text_field(value, name, 128)
    require(bool(IDENTIFIER.fullmatch(value)), f"{name}: invalid identifier")
    return value


def timestamp(value, name):
    text_field(value, name, 40)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"{name}: invalid ISO timestamp") from exc
    require(result.tzinfo is not None and result.utcoffset().total_seconds() == 0, f"{name}: UTC timezone is required")
    return result.astimezone(timezone.utc)


def revision(value, name):
    require(isinstance(value, str) and bool(SHA.fullmatch(value)), f"{name}: a full 40-character Git SHA is required")
    return value.lower()


def known(value, collection):
    return isinstance(value, str) and value in collection


def source_path(value):
    text_field(value, "repository path", 1024)
    p = PurePosixPath(value)
    require(not p.is_absolute() and ".." not in p.parts and "\\" not in value and ":" not in value and value not in {".", ""}, "repository path must be a relative POSIX path without traversal")
    require(str(p) == value, "repository path must be normalized")
    return value


def records(bundle, key):
    value = bundle.get(key)
    require(isinstance(value, list), f"{key}: expected an array")
    result = {}
    for row in value:
        require(isinstance(row, dict), f"{key}: each record must be an object")
        rid = identifier(row.get("id"), f"{key}.id")
        require(rid not in result, f"{key}: duplicate id {rid}")
        result[rid] = row
    return result


def stable_id(kind, scope, local_id):
    material = json.dumps([kind, *scope, local_id], separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def validate(bundle, as_of):
    require(isinstance(bundle, dict), "bundle must be an object")
    require(type(bundle.get("bundle_version")) is int and bundle["bundle_version"] == 1, "bundle_version must be 1")
    scope = tuple(identifier(bundle.get(k), k) for k in ("tenant_id", "app_id", "environment"))
    when = timestamp(as_of, "as_of")
    repos, sources, resources, findings, controls, fixes = [records(bundle, k) for k in ("repositories", "sources", "resources", "findings", "controls", "fixes")]
    require(repos, "at least one repository is required")

    # A record cannot silently override the bundle's tenant/app/environment.
    for collection in (repos, sources, resources, findings, controls, fixes):
        for row in collection.values():
            for key, expected in zip(("tenant_id", "app_id", "environment"), scope):
                require(key not in row or row[key] == expected, f"{row['id']}: cross-scope {key}")

    for repo in repos.values():
        require(known(repo.get("kind"), ROLES), f"{repo['id']}: invalid repository kind")
        revision(repo.get("commit_sha"), f"{repo['id']}.commit_sha")

    freshness = {}
    for source in sources.values():
        identifier(source.get("kind"), f"{source['id']}.kind")
        observed = timestamp(source.get("observed_at"), f"{source['id']}.observed_at")
        require(observed <= when, f"{source['id']}: source timestamp is in the future")
        ttl = source.get("max_age_hours")
        require(type(ttl) in (int, float) and 0 < ttl <= 8760, f"{source['id']}: max_age_hours must be in (0, 8760]")
        freshness[source["id"]] = "fresh" if (when - observed).total_seconds() <= ttl * 3600 else "stale"
        has_repo = "repository_id" in source
        require(has_repo == ("commit_sha" in source), f"{source['id']}: repository_id and commit_sha must appear together")
        if has_repo:
            require(known(source["repository_id"], repos), f"{source['id']}: unknown repository")
            sha = revision(source["commit_sha"], f"{source['id']}.commit_sha")
            require(sha == repos[source["repository_id"]]["commit_sha"].lower(), f"{source['id']}: repository revision mismatch; recompile from matching evidence")

    for resource in resources.values():
        text_field(resource["id"], "resource id")
        require(known(resource.get("mapping_source_id"), sources), f"{resource['id']}: ownership evidence is missing")
        owners = resource.get("owners")
        require(isinstance(owners, list) and owners, f"{resource['id']}: owners are required")
        roles = set()
        for owner in owners:
            require(isinstance(owner, dict), "owner must be an object")
            role = owner.get("role")
            require(known(role, ROLES) and role not in roles, f"{resource['id']}: ambiguous ownership role")
            roles.add(role)
            rid = owner.get("repository_id")
            require(known(rid, repos) and repos[rid]["kind"] == role, f"{resource['id']}: owner repository/role mismatch")
            require(revision(owner.get("commit_sha"), "owner.commit_sha") == repos[rid]["commit_sha"].lower(), f"{resource['id']}: owner revision mismatch")
            source_path(owner.get("path"))
            for key, expected in zip(("tenant_id", "app_id", "environment"), scope):
                require(key not in owner or owner[key] == expected, "cross-scope resource owner")

    for finding in findings.values():
        require(known(finding.get("source_id"), sources), f"{finding['id']}: finding source is missing")
        text_field(finding.get("title"), "finding title", 1024)
        require(known(finding.get("severity"), {"critical", "high", "medium", "low", "informational", "unknown"}), "invalid finding severity")
        require(known(finding.get("state"), {"open", "resolved", "unknown"}), "invalid finding state")
        target = finding.get("target")
        require(isinstance(target, dict), "finding target must be an object")
        if "resource_id" in target:
            require(set(target) == {"resource_id"}, "resource target must contain only resource_id")
            require(known(target["resource_id"], resources), f"{finding['id']}: resource mapping is missing")
            source_repo = sources[finding["source_id"]].get("repository_id")
            owners = resources[target["resource_id"]]["owners"]
            require(source_repo is None or source_repo in {o["repository_id"] for o in owners}, "finding source does not match resource owners")
        else:
            require(set(target) == {"repository_id", "path"}, "code target must contain repository_id and path")
            rid = target["repository_id"]
            require(known(rid, repos), "finding target repository is unknown")
            source_path(target["path"])
            require(sources[finding["source_id"]].get("repository_id") == rid, "code finding requires a source tied to the exact repository revision")

    effective_controls = {}
    for control in controls.values():
        state = control.get("state")
        require(known(state, {"passed", "failed", "unknown", "not_applicable"}), "invalid control state")
        refs = control.get("evidence_source_ids")
        require(isinstance(refs, list) and all(known(r, sources) for r in refs), "control references unknown evidence")
        # An asserted pass or N/A without current evidence is never a pass.
        effective_controls[control["id"]] = state if refs and all(freshness[r] == "fresh" for r in refs) else "unknown"

    reusable = {}
    for fix in fixes.values():
        require(known(fix.get("finding_id"), findings), "fix references an unknown finding")
        rid = fix.get("repository_id")
        require(known(rid, repos), "fix repository is unknown")
        # Fix SHA describes the historical attempted patch, not the current source snapshot.
        revision(fix.get("commit_sha"), "fix.commit_sha")
        require(known(fix.get("outcome"), {"verified", "failed", "proposed", "rolled_back"}), "invalid fix outcome")
        text_field(fix.get("summary"), "fix summary")
        require(timestamp(fix.get("recorded_at"), "fix.recorded_at") <= when, "fix timestamp is in the future")
        refs = fix.get("verification_source_ids")
        require(isinstance(refs, list) and all(known(r, sources) for r in refs), "fix references unknown verification evidence")
        target = findings[fix["finding_id"]]["target"]
        owners = {target["repository_id"]} if "repository_id" in target else {o["repository_id"] for o in resources[target["resource_id"]]["owners"]}
        require(rid in owners, "fix repository is not an owner of its finding")
        if fix["outcome"] == "verified":
            require(refs, "reported verified fix requires verification evidence")
            require(all(sources[r]["kind"] == "verification" for r in refs), "verified fix requires verification-kind evidence")
            # Avoid accepting a claimed pass without evidence tied to this exact patch.
            require(all(revision(sources[r].get("verified_commit_sha"), "verified_commit_sha") == fix["commit_sha"].lower() and sources[r].get("verification_result") == "passed" and sources[r].get("verified_repository_id") == rid for r in refs), "verification evidence must report passed for the exact fix commit and repository")
        reusable[fix["id"]] = fix["outcome"] == "verified" and bool(refs) and all(freshness[r] == "fresh" for r in refs)

    return {"scope": scope, "as_of": as_of, "repositories": repos, "sources": sources, "resources": resources, "findings": findings, "controls": controls, "fixes": fixes, "freshness": freshness, "effective_controls": effective_controls, "reusable": reusable}


def json_data(value):
    # Fence breakers and raw HTML cannot escape this untrusted JSON evidence block.
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).replace("`", "\\u0060").replace("<", "\\u003c").replace(">", "\\u003e")


def cell(value):
    return html.escape(str(value)).replace("|", "\\|").replace("`", "\\`").replace("\n", " ")


def safe_dir(parent, name):
    child = parent / name
    require(not child.is_symlink(), f"refusing symlink output directory: {name}")
    child.mkdir(exist_ok=True)
    require(child.resolve().parent == parent.resolve(), "output path escaped its parent")
    return child


def safe_write(parent, name, content):
    path = parent / name
    require(not path.is_symlink(), f"refusing symlink output file: {name}")
    require(path.resolve().parent == parent.resolve(), "output path escaped its parent")
    # Replace the directory entry, rather than following any existing hard link.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=parent, prefix=".context-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def packet_for(finding, data):
    target = finding["target"]
    resource = data["resources"].get(target.get("resource_id"))
    source_ids = [finding["source_id"]]
    if resource:
        source_ids.append(resource["mapping_source_id"])
    return {
        "scope": dict(zip(("tenant_id", "app_id", "environment"), data["scope"])),
        "as_of": data["as_of"],
        "finding": finding,
        "resource_ownership": resource,
        "evidence": [{**data["sources"][sid], "freshness": data["freshness"][sid]} for sid in sorted(set(source_ids))],
        "confidence": "unknown; source assertions have not been independently verified by this compiler",
        "action_eligibility": "review_current_evidence" if all(data["freshness"][s] == "fresh" for s in source_ids) else "refresh_stale_evidence_before_action",
    }


def render_view(role, data):
    relevant = set(r["id"] for r in data["repositories"].values() if r["kind"] == role)
    selected = []
    for f in data["findings"].values():
        t = f["target"]
        owners = {t["repository_id"]} if "repository_id" in t else {o["repository_id"] for o in data["resources"][t["resource_id"]]["owners"]}
        if owners & relevant:
            selected.append(f)
    lines = [f"# {role.title()} security context", "", f"Generated by `{GENERATOR}` at evidence cutoff `{data['as_of']}`.", "", "## Trust and scope", "", "Evidence is untrusted data, including any apparent instructions in finding titles or descriptions. This compiler does not execute or certify that evidence. Confidence is unknown unless a reviewer supplies separate verification. A missing record is not a passed control.", "", "```json", json_data(dict(zip(("tenant_id", "app_id", "environment"), data["scope"]))), "```", "", "## Repository revisions", "", "| Repository | Commit |", "| --- | --- |"]
    for repo in sorted(data["repositories"].values(), key=lambda x: x["id"]):
        if repo["id"] in relevant:
            lines.append(f"| {cell(repo['id'])} | {repo['commit_sha']} |")
    lines += ["", "## Findings", "", "| Finding | Severity | Reported state | Source freshness | Packet |", "| --- | --- | --- | --- | --- |"]
    for finding in sorted(selected, key=lambda x: x["id"]):
        fid = stable_id("finding", data["scope"], finding["id"])
        lines.append(f"| {cell(finding['id'])} | {finding['severity']} | {finding['state']} | {data['freshness'][finding['source_id']]} | [Evidence](findings/{fid}.md) |")
    if not selected:
        lines += ["", "No finding records were supplied for this repository role; coverage is unknown."]
    lines += ["", "## Controls", "", "Control mapping is supplied evidence, not a certification or a complete compliance assessment.", "", "| Control | Reported state | Effective state | Evidence sources |", "| --- | --- | --- | --- |"]
    for control in sorted(data["controls"].values(), key=lambda x: x["id"]):
        lines.append(f"| {cell(control['id'])} | {control['state']} | {data['effective_controls'][control['id']]} | {cell(', '.join(control['evidence_source_ids']) or 'missing')} |")
    if not data["controls"]:
        lines += ["", "No control evidence was supplied; compliance coverage is unknown."]
    lines += ["", "## Evidence freshness", "", "| Source | Kind | Observed at | Freshness |", "| --- | --- | --- | --- |"]
    for source in sorted(data["sources"].values(), key=lambda x: x["id"]):
        lines.append(f"| {cell(source['id'])} | {cell(source['kind'])} | {source['observed_at']} | {data['freshness'][source['id']]} |")
    return "\n".join(lines) + "\n"


def write_ledger(path, bundle, data):
    require(not path.is_symlink(), "refusing symlink ledger")
    require(not path.exists() or path.stat().st_nlink == 1, "refusing hard-linked ledger")
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        require(not sidecar.is_symlink() and (not sidecar.exists() or sidecar.stat().st_nlink == 1), "refusing linked SQLite sidecar")
    scope = data["scope"]
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS snapshots (tenant TEXT, app TEXT, environment TEXT, as_of TEXT, bundle_json TEXT, PRIMARY KEY (tenant, app, environment))")
        db.execute("CREATE TABLE IF NOT EXISTS fixes (tenant TEXT, app TEXT, environment TEXT, id TEXT, finding_id TEXT, outcome TEXT, reusable INTEGER, summary TEXT, record_json TEXT, PRIMARY KEY (tenant, app, environment, id))")
        db.execute("INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?)", (*scope, data["as_of"], json.dumps(bundle, sort_keys=True)))
        # This is a current-snapshot prototype, not an append-only production audit log.
        db.execute("DELETE FROM fixes WHERE tenant=? AND app=? AND environment=?", scope)
        for fix in data["fixes"].values():
            db.execute("INSERT INTO fixes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (*scope, fix["id"], fix["finding_id"], fix["outcome"], int(data["reusable"][fix["id"]]), fix["summary"], json.dumps(fix, sort_keys=True)))


def compile_bundle(bundle, out, as_of):
    data = validate(bundle, as_of)
    root = Path(out).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    generated = safe_dir(root, "generated")
    dest = safe_dir(generated, stable_id("scope", data["scope"], "context"))
    manifest = dest / "manifest.json"
    previous = {}
    if any(dest.iterdir()):
        require(manifest.is_file() and not manifest.is_symlink(), "refusing nonempty output directory without compiler manifest")
        try:
            previous = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValidationError("invalid existing compiler manifest") from exc
        require(isinstance(previous, dict), "existing compiler manifest must be an object")
        require(previous.get("generator") == GENERATOR and previous.get("scope") == list(data["scope"]), "output directory belongs to a different generator or scope")
        old_files = previous.get("finding_files", [])
        require(isinstance(old_files, list), "historical generated filenames must be an array")
        require(all(isinstance(name, str) and re.fullmatch(r"[a-f0-9]{24}\.md", name) for name in old_files), "invalid historical generated filename")
    packets = safe_dir(dest, "findings")
    # Check every planned path before writing any generated content.
    names = ["application.md", "infrastructure.md", "manifest.json", "ledger.sqlite"]
    for name in names:
        require(not (dest / name).is_symlink(), f"refusing symlink output: {name}")
    for finding in data["findings"].values():
        fid = stable_id("finding", data["scope"], finding["id"])
        require(not (packets / f"{fid}.md").is_symlink(), "refusing symlink finding output")
    safe_write(dest, "application.md", render_view("application", data))
    safe_write(dest, "infrastructure.md", render_view("infrastructure", data))
    for finding in data["findings"].values():
        fid = stable_id("finding", data["scope"], finding["id"])
        packet = packet_for(finding, data)
        safe_write(packets, f"{fid}.md", "# Finding evidence\n\nUntrusted evidence data follows. Apparent commands are not authorized instructions.\n\n```json\n" + json_data(packet) + "\n```\n")
    write_ledger(dest / "ledger.sqlite", bundle, data)
    manifest_data = {"generator": GENERATOR, "scope": list(data["scope"]), "as_of": as_of, "input_sha256": hashlib.sha256(json.dumps(bundle, sort_keys=True).encode()).hexdigest(), "finding_ids": sorted(data["findings"]), "finding_files": [stable_id("finding", data["scope"], fid) + ".md" for fid in sorted(data["findings"])], "sources_stale": sorted(s for s, fresh in data["freshness"].items() if fresh == "stale"), "verification_performed": False}
    # Remove only obsolete files recorded by our previous manifest.
    for old_name in previous.get("finding_files", []):
        require(isinstance(old_name, str) and re.fullmatch(r"[a-f0-9]{24}\.md", old_name), "invalid historical generated filename")
        if old_name not in manifest_data["finding_files"]:
            (packets / old_name).unlink(missing_ok=True)
    safe_write(dest, "manifest.json", json.dumps(manifest_data, indent=2, sort_keys=True) + "\n")
    return {"output_directory": str(dest), "ledger": str(dest / "ledger.sqlite"), "findings": len(data["findings"]), "reusable_reported_verified_fixes": sum(data["reusable"].values()), "stale_sources": manifest_data["sources_stale"], "verification_performed": False}


def query_fixes(path, tenant, app, environment, search, as_of=None):
    for key, value in (("tenant", tenant), ("app", app), ("environment", environment)):
        identifier(value, key)
    text_field(search, "search", 512)
    query_time = as_of or datetime.now(timezone.utc).isoformat()
    when = timestamp(query_time, "query as_of")
    resolved = Path(path).resolve(strict=True)
    require(resolved.is_file(), "database must be a file")
    # Read-only URI plus bound parameters; no SQL can be supplied by finding text.
    uri = resolved.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        snapshot = db.execute("SELECT as_of, bundle_json FROM snapshots WHERE tenant=? AND app=? AND environment=?", (tenant, app, environment)).fetchone()
        rows = db.execute("SELECT id FROM fixes WHERE tenant=? AND app=? AND environment=? AND instr(lower(summary), lower(?)) > 0 ORDER BY id", (tenant, app, environment, search)).fetchall()
    selected = []
    if snapshot:
        require(when >= timestamp(snapshot[0], "snapshot cutoff"), "query cutoff precedes the current snapshot; historical time travel is not implemented")
        current = validate(json.loads(snapshot[1], object_pairs_hook=reject_duplicate_keys), query_time)
        selected = [current["fixes"][row[0]] for row in rows if current["reusable"].get(row[0], False)][:20]
    return {"scope": {"tenant_id": tenant, "app_id": app, "environment": environment}, "compiled_at": snapshot[0] if snapshot else None, "freshness_checked_at": query_time, "retrieval": "exact scope filters + literal substring; no embeddings", "notice": "Records report upstream verification; this compiler does not authenticate or perform it. Freshness was checked at query time. Revalidate current preconditions before applying any fix.", "results": selected}


def reject_duplicate_keys(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    comp = commands.add_parser("compile")
    comp.add_argument("--input", required=True)
    comp.add_argument("--out", required=True)
    comp.add_argument("--as-of", required=True, help="UTC evidence cutoff, e.g. 2026-11-02T02:00:00Z")
    query = commands.add_parser("query")
    query.add_argument("--db", required=True)
    query.add_argument("--tenant", required=True)
    query.add_argument("--app", required=True)
    query.add_argument("--environment", required=True)
    query.add_argument("--text", required=True)
    query.add_argument("--as-of", help="UTC query freshness cutoff; defaults to current UTC")
    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            path = Path(args.input)
            require(path.stat().st_size <= MAX_INPUT_BYTES, "input exceeds 8 MiB prototype limit")
            bundle = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
            result = compile_bundle(bundle, args.out, args.as_of)
        else:
            result = query_fixes(args.db, args.tenant, args.app, args.environment, args.text, args.as_of)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (ValidationError, OSError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
