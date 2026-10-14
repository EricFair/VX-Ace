"""Keep the isolated dependency identical to its recorded upstream snapshot."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PinnedDependencyTests(unittest.TestCase):
    def test_all_adopted_files_match_provenance_and_no_writer_is_vendored(self):
        manifest = json.loads((ROOT / "tools/_vendor/manifest.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(manifest["commit"], "75d7360fc12eda3046881e0424f136a9a5c01487")
        self.assertEqual(manifest["license_declaration"], "MIT")
        for entry in manifest["files"]:
            with self.subTest(path=entry["destination"]):
                content = (ROOT / entry["destination"]).read_bytes()
                # Preserve exact archived bytes across platforms through
                # .gitattributes rather than normalizing this pinned subset.
                self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
        modules = {p.name for p in (ROOT / "tools/_vendor/rpgvxace_mcp").glob("*.py")}
        self.assertEqual(modules, {"__init__.py", "marshal_rb.py", "rubytypes.py"})
