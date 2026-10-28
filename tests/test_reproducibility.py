"""
tests/test_reproducibility.py — Fixed-seed reproducibility test.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import hashlib
import tempfile
import json
from pathlib import Path

from schedgen.__main__ import run


def _checksum_dir(d: Path) -> dict[str, str]:
    result = {}
    for f in sorted(d.glob("*.csv")):
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        result[f.name] = h
    return result


def test_reproducibility_starter():
    with tempfile.TemporaryDirectory() as tmp:
        out1 = os.path.join(tmp, "run1")
        out2 = os.path.join(tmp, "run2")
        run("starter", out1, inject=False)
        run("starter", out2, inject=False)
        cs1 = _checksum_dir(Path(out1))
        cs2 = _checksum_dir(Path(out2))
        assert cs1 == cs2, f"Checksums differ:\n{cs1}\nvs\n{cs2}"


def test_row_counts_starter():
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "run")
        run("starter", out, inject=False)
        manifest = json.loads((Path(out) / "manifest.json").read_text())
        assert manifest["files"]["products.csv"]["rows"] == 5
        assert manifest["files"]["machines.csv"]["rows"] == 3
        assert manifest["files"]["orders.csv"]["rows"] == 10
        assert manifest["files"]["materials.csv"]["rows"] == 5
