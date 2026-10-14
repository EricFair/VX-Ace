"""Run the pinned upstream codec conformance suite without its MCP/writer layer."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "_vendor"))


def load_tests(loader, tests, pattern):
    spec = importlib.util.spec_from_file_location(
        "pinned_upstream_marshal_tests", Path(__file__).with_name("upstream_marshal.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
