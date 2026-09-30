#!/usr/bin/env python3
"""Check inventory hashes, physical page locations, and published data consistency."""

import csv
import hashlib
import json
import subprocess
from pathlib import Path

try:
    from .build_data import EXCLUDED_FILES, PDF_DIR, ROOT, report_pages
except ImportError:
    from build_data import EXCLUDED_FILES, PDF_DIR, ROOT, report_pages


def main():
    manifest = json.loads((ROOT / "data/report_sources.json").read_text())
    payload = json.loads((ROOT / "docs/assets/comments.json").read_text())
    assert not manifest["failures"], "Archive downloads remain unresolved"
    assert payload["reports"] == manifest["reports"]
    reports = {r["source_file"]: r for r in manifest["reports"]}
    assert len(reports) == len(manifest["reports"]), "Duplicate report filename"
    assert not set(reports).intersection(EXCLUDED_FILES)
    paragraphs = {}
    for name, report in reports.items():
        pdf = PDF_DIR / name
        assert hashlib.sha256(pdf.read_bytes()).hexdigest() == report["sha256"], name
        pages, blocks = report_pages(pdf)
        info = subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True).stdout
        physical_pages = int(next(line.split(":", 1)[1].strip() for line in info.splitlines() if line.startswith("Pages:")))
        assert len(pages) == physical_pages == report["pages"], (name, "Physical page mismatch")
        paragraphs[name] = blocks
    for row in payload["records"]:
        name = row["source_file"]
        assert name in reports, name
        block = paragraphs[name][row["paragraph_index"] - 1]
        assert block["page"] == row["page"] and block["text"] == row["full_text"], (name, row["id"])
        assert row["year"] == reports[name]["year"] and row["month"] == reports[name]["month"]
        assert row["page_url"] == row["pdf_url"] + f"#page={row['page']}"
    js = (ROOT / "docs/assets/comments-data.js").read_text()
    assert json.loads(js.removeprefix("window.SSC_COMMENTS_DATA = ").rstrip(";\n")) == payload
    with (ROOT / "data/processed/ssc_stock_comments.csv").open(newline="") as source:
        assert sum(1 for _ in csv.DictReader(source)) == len(payload["records"])
    print(f"Verified {len(reports)} PDF hashes and physical page counts; {len(payload['records'])} exact source paragraphs; CSV/JSON/local JS agree.")


if __name__ == "__main__":
    main()
