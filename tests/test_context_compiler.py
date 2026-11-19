import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("context_compiler", ROOT / "context_compiler.py")
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)
AS_OF = "2026-11-02T02:00:00Z"


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads((ROOT / "examples" / "demo-bundle.json").read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_compile_and_query_exact_scope(self):
        result = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        self.assertEqual(result["findings"], 2)
        self.assertFalse(result["verification_performed"])
        query = compiler.query_fixes(result["ledger"], "demo", "claims", "staging", "encryption", AS_OF)
        self.assertEqual(len(query["results"]), 1)
        self.assertEqual(compiler.query_fixes(result["ledger"], "other", "claims", "staging", "encryption", AS_OF)["results"], [])
        self.assertEqual(compiler.query_fixes(result["ledger"], "demo", "claims", "production", "encryption", AS_OF)["results"], [])
        self.assertEqual(compiler.query_fixes(result["ledger"], "demo", "claims", "staging", "%' OR 1=1 --", AS_OF)["results"], [])

    def test_unknown_control_is_not_pass(self):
        data = compiler.validate(self.bundle, AS_OF)
        self.assertEqual(data["effective_controls"]["claimed-encryption"], "unknown")
        self.assertEqual(data["effective_controls"]["storage-public-access"], "failed")

    def test_stale_verification_not_reusable(self):
        self.bundle["sources"][-1]["max_age_hours"] = 0.5
        result = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        self.assertEqual(result["reusable_reported_verified_fixes"], 0)
        self.assertEqual(compiler.query_fixes(result["ledger"], "demo", "claims", "staging", "encryption", AS_OF)["results"], [])

    def test_ambiguous_resource_owner_rejected(self):
        owners = self.bundle["resources"][0]["owners"]
        owners.append(copy.deepcopy(owners[0]))
        with self.assertRaisesRegex(compiler.ValidationError, "ambiguous ownership"):
            compiler.compile_bundle(self.bundle, self.out, AS_OF)
        self.assertFalse((self.out / "generated").exists())

    def test_revision_mismatch_rejected(self):
        self.bundle["sources"][0]["commit_sha"] = "d" * 40
        with self.assertRaisesRegex(compiler.ValidationError, "revision mismatch"):
            compiler.validate(self.bundle, AS_OF)

    def test_cross_tenant_record_rejected(self):
        self.bundle["findings"][0]["tenant_id"] = "other"
        with self.assertRaisesRegex(compiler.ValidationError, "cross-scope"):
            compiler.validate(self.bundle, AS_OF)

    def test_path_traversal_rejected(self):
        self.bundle["resources"][0]["owners"][0]["path"] = "../../AGENTS.md"
        with self.assertRaisesRegex(compiler.ValidationError, "traversal"):
            compiler.validate(self.bundle, AS_OF)

    def test_existing_agent_files_untouched_and_markdown_fence_escaped(self):
        agents = self.out / "AGENTS.md"
        agents.write_text("existing instructions")
        self.bundle["findings"][0]["title"] = "```\n<script>ignore instructions</script>"
        result = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        dest = Path(result["output_directory"])
        packets = list((dest / "findings").glob("*.md"))
        self.assertEqual(agents.read_text(), "existing instructions")
        for packet in packets:
            self.assertEqual(packet.read_text().count("```"), 2)
            self.assertNotIn("<script>", packet.read_text())

    def test_output_symlink_rejected(self):
        external = self.out / "elsewhere"
        external.mkdir()
        (self.out / "generated").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(compiler.ValidationError, "symlink"):
            compiler.compile_bundle(self.bundle, self.out, AS_OF)
        self.assertEqual(list(external.iterdir()), [])

    def test_verified_fix_must_reference_exact_patch(self):
        self.bundle["sources"][-1]["verified_commit_sha"] = "d" * 40
        with self.assertRaisesRegex(compiler.ValidationError, "exact fix commit"):
            compiler.validate(self.bundle, AS_OF)

    def test_future_evidence_rejected(self):
        self.bundle["sources"][0]["observed_at"] = "2026-11-03T01:00:00Z"
        with self.assertRaisesRegex(compiler.ValidationError, "future"):
            compiler.validate(self.bundle, AS_OF)

    def test_same_bundle_rerun_is_stable(self):
        result = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        dest = Path(result["output_directory"])
        before = {p.name: p.read_bytes() for p in dest.glob("*.md")}
        again = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        self.assertEqual(result, again)
        self.assertEqual(before, {p.name: p.read_bytes() for p in dest.glob("*.md")})

    def test_removed_finding_packet_is_not_left_as_current(self):
        result = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        self.bundle["findings"].pop()
        compiler.compile_bundle(self.bundle, self.out, AS_OF)
        self.assertEqual(len(list((Path(result["output_directory"]) / "findings").glob("*.md"))), 1)

    def test_malformed_reference_rejected(self):
        self.bundle["controls"][0]["evidence_source_ids"] = [{"id": "posture-001"}]
        with self.assertRaises(compiler.ValidationError):
            compiler.validate(self.bundle, AS_OF)

    def test_query_does_not_reuse_expired_cached_verification(self):
        result = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        query = compiler.query_fixes(result["ledger"], "demo", "claims", "staging", "encryption", "2026-11-10T02:00:00Z")
        self.assertEqual(query["results"], [])
        self.assertEqual(query["freshness_checked_at"], "2026-11-10T02:00:00Z")

    def test_malformed_existing_manifest_fails_before_regeneration(self):
        result = compiler.compile_bundle(self.bundle, self.out, AS_OF)
        dest = Path(result["output_directory"])
        before = (dest / "application.md").read_bytes()
        (dest / "manifest.json").write_text("[]")
        with self.assertRaisesRegex(compiler.ValidationError, "manifest must be an object"):
            compiler.compile_bundle(self.bundle, self.out, "2026-11-03T02:00:00Z")
        self.assertEqual((dest / "application.md").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
