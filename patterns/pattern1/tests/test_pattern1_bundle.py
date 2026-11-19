import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[3]
PATTERN = ROOT / "patterns" / "pattern1"
SPE = importlib.util.spec_from_file_location("pattern1_bundle", PATTERN / "scripts" / "build_bundle.py")
module = importlib.util.module_from_spec(SPE)
SPE.loader.exec_module(module)
AS_OF = "2026-11-19T12:15:00Z"
APP_SHA = "a" * 40
INFRA_SHA = "b" * 40


class Pattern1Tests(unittest.TestCase):
    def setUp(self):
        self.deployment = json.loads((PATTERN / "fixtures" / "deployment.example.json").read_text())
        self.scans = json.loads((PATTERN / "fixtures" / "normalized-scans.example.json").read_text())

    def test_fixture_matches_assembly_and_compiles(self):
        expected = json.loads((PATTERN / "fixtures" / "bundle.example.json").read_text())
        bundle = module.assemble(self.deployment, self.scans, APP_SHA, INFRA_SHA)
        self.assertEqual(bundle, expected)
        with tempfile.TemporaryDirectory() as root:
            compiled = module.compiler.compile_bundle(bundle, root, AS_OF)
            self.assertEqual(compiled["findings"], 3)
            self.assertFalse(compiled["verification_performed"])

    def test_wrong_deployment_sha_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "deployment commit"):
            module.assemble(self.deployment, self.scans, "f" * 40, INFRA_SHA)

    def test_wrong_scan_sha_fails_closed(self):
        self.scans["sources"][0]["commit_sha"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "scanner source SHA"):
            module.assemble(self.deployment, self.scans, APP_SHA, INFRA_SHA)

    def test_cloud_account_mismatch_rejected(self):
        self.scans["sources"][1]["aws_account_id"] = "000000000000"
        with self.assertRaisesRegex(ValueError, "scan AWS account"):
            module.assemble(self.deployment, self.scans, APP_SHA, INFRA_SHA)

    def test_missing_scans_not_interpreted_as_clean(self):
        self.scans["sources"].clear()
        with self.assertRaisesRegex(ValueError, "at least one"):
            module.assemble(self.deployment, self.scans, APP_SHA, INFRA_SHA)

    def test_unmapped_cloud_resource_rejected(self):
        self.scans["sources"][2]["findings"][0]["resource_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unresolved deployed resource"):
            module.assemble(self.deployment, self.scans, APP_SHA, INFRA_SHA)


if __name__ == "__main__":
    unittest.main()
