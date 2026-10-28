"""
scripts/repro_check.py — Reproducibility verification.

Runs the generator twice with the same seed and profile, then compares:
  - Row counts from manifest.json
  - SHA-256 checksums of all CSV files

Exits 0 on match, 1 on any mismatch.

Usage:
  python scripts/repro_check.py --profile starter
  python scripts/repro_check.py --profile full
"""

from __future__ import annotations
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schedgen.__main__ import run


def _csv_checksums(directory: Path) -> dict[str, str]:
    return {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(directory.glob("*.csv"))
    }


def _row_counts(directory: Path) -> dict[str, int]:
    manifest = json.loads((directory / "manifest.json").read_text())
    return {
        name: info["rows"]
        for name, info in manifest["files"].items()
        if name.endswith(".csv") and "rows" in info
    }


def main():
    parser = argparse.ArgumentParser(description="YottaFlex reproducibility check")
    parser.add_argument("--profile", choices=["starter", "full"], default="starter")
    args = parser.parse_args()

    print(f"[repro_check] profile={args.profile}  running two independent generations ...")

    with tempfile.TemporaryDirectory() as tmp:
        out1 = Path(tmp) / "run1"
        out2 = Path(tmp) / "run2"

        run(args.profile, str(out1), inject=False)
        run(args.profile, str(out2), inject=False)

        cs1 = _csv_checksums(out1)
        cs2 = _csv_checksums(out2)
        rc1 = _row_counts(out1)
        rc2 = _row_counts(out2)

    ok = True

    # Row count comparison
    if rc1 == rc2:
        print(f"  [PASS] Row counts match across {len(rc1)} files")
    else:
        ok = False
        print("  [FAIL] Row count mismatch:")
        for name in sorted(set(rc1) | set(rc2)):
            if rc1.get(name) != rc2.get(name):
                print(f"    {name}: run1={rc1.get(name)}  run2={rc2.get(name)}")

    # Checksum comparison
    if cs1 == cs2:
        print(f"  [PASS] CSV checksums match across {len(cs1)} files")
    else:
        ok = False
        print("  [FAIL] Checksum mismatch:")
        for name in sorted(set(cs1) | set(cs2)):
            if cs1.get(name) != cs2.get(name):
                print(f"    {name}")
                print(f"      run1: {cs1.get(name)}")
                print(f"      run2: {cs2.get(name)}")

    if ok:
        print(f"\n  Reproducibility VERIFIED for profile={args.profile}")
        sys.exit(0)
    else:
        print(f"\n  Reproducibility FAILED for profile={args.profile}")
        sys.exit(1)


if __name__ == "__main__":
    main()
