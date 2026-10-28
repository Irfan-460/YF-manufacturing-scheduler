"""
export.py — Write CSV, JSON, and SQL seed files; produce manifest.
"""

from __future__ import annotations
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def export_all(
    out_dir: str,
    tables: dict[str, pd.DataFrame],
    ground_truth: pd.DataFrame,
    metrics: dict,
    violations: pd.DataFrame,
    seed: int,
    profile: str,
) -> dict:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    gt_dir = Path(out_dir).parent.parent / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at": "2026-01-05T00:00:00",
        "seed": seed,
        "profile": profile,
        "files": {},
    }

    # ── CSV ──────────────────────────────────────────────────────────────────
    for name, df in tables.items():
        p = base / f"{name}.csv"
        df.to_csv(p, index=False)
        manifest["files"][f"{name}.csv"] = {
            "rows": len(df),
            "sha256": _sha256(p),
        }

    # ── Ground truth ─────────────────────────────────────────────────────────
    gt_csv  = gt_dir / f"ground_truth_{profile}.csv"
    gt_json = gt_dir / f"ground_truth_{profile}.json"
    ground_truth.to_csv(gt_csv, index=False)
    ground_truth.to_json(gt_json, orient="records", indent=2)
    manifest["files"]["ground_truth.csv"] = {
        "rows": len(ground_truth),
        "sha256": _sha256(gt_csv),
    }

    # ── Violations ───────────────────────────────────────────────────────────
    viol_path = base / "violations.csv"
    violations.to_csv(viol_path, index=False)
    manifest["files"]["violations.csv"] = {
        "rows": len(violations),
        "sha256": _sha256(viol_path),
    }

    # ── Metrics JSON ─────────────────────────────────────────────────────────
    metrics_out = {k: v for k, v in metrics.items() if k != "machine_utilization"}
    metrics_path = base / "metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_out, f, indent=2)

    util_path = base / "machine_utilization.csv"
    if isinstance(metrics.get("machine_utilization"), pd.DataFrame):
        metrics["machine_utilization"].to_csv(util_path, index=False)

    # ── SQL seed ─────────────────────────────────────────────────────────────
    sql_path = base / "seed.sql"
    _write_sql(sql_path, tables)
    manifest["files"]["seed.sql"] = {"sha256": _sha256(sql_path)}

    # ── Manifest ─────────────────────────────────────────────────────────────
    manifest_path = base / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


def _write_sql(path: Path, tables: dict[str, pd.DataFrame]):
    with open(path, "w", encoding="utf-8") as f:
        for name, df in tables.items():
            if df.empty:
                continue
            cols = ", ".join(df.columns)
            f.write(f"-- {name}\n")
            for _, row in df.iterrows():
                vals = ", ".join(
                    "NULL" if (v is None or (isinstance(v, float) and pd.isna(v)))
                    else f"'{str(v).replace(chr(39), chr(39)*2)}'"
                    for v in row
                )
                f.write(f"INSERT INTO {name} ({cols}) VALUES ({vals});\n")
            f.write("\n")
