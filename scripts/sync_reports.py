#!/usr/bin/env python3
"""Import SSC-column PDFs from the public Council Records archive."""

import argparse
import hashlib
import json
import re
import subprocess
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from .build_data import EXCLUDED_FILES, PDF_DIR, ROOT, extract_pages, report_date
    from .ocr_report import ocr_pages
except ImportError:
    from build_data import EXCLUDED_FILES, PDF_DIR, ROOT, extract_pages, report_date
    from ocr_report import ocr_pages

ARCHIVE = "https://www.npfmc.org/library/council-records/"
MANIFEST = ROOT / "data" / "report_sources.json"
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")


def month_name(text):
    for month in MONTHS:
        if re.search(r"(?<![a-z])" + month[:3] + r"[a-z]*(?![a-z])", text, re.I):
            return month
    return ""


class ArchiveParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None
        self.link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"text": "", "links": []}
        elif tag == "a" and self.cell is not None:
            self.link = {"url": attrs.get("href", ""), "label": ""}

    def handle_data(self, text):
        if self.cell is not None:
            self.cell["text"] += text
        if self.link is not None:
            self.link["label"] += text

    def handle_endtag(self, tag):
        if tag == "a" and self.link is not None:
            self.cell["links"].append(self.link)
            self.link = None
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def discover(html, since, as_of):
    parser = ArchiveParser()
    parser.feed(html)
    reports = {}
    for cells in parser.rows:
        if len(cells) < 4 or not re.fullmatch(r"\s*20\d\d\s*", cells[0]["text"]):
            continue
        year = int(cells[0]["text"].strip())
        for link in cells[3]["links"]:
            month = month_name(link["label"])
            if not month or "SSC" not in link["label"].upper():
                continue
            if year < since or date(year, MONTHS.index(month) + 1, 1) > as_of:
                continue
            url = urljoin(ARCHIVE, link["url"])
            if url.startswith("http://"):
                url = "https://" + url[7:]
            validate_url(url)
            key = (year, month)
            report = {"year": str(year), "month": month, "archive_url": ARCHIVE,
                      "official_report_url": url, "archive_label": link["label"].strip()}
            if len(cells) > 4 and cells[4]["links"]:
                report["meeting_url"] = cells[4]["links"][0]["url"]
            if key in reports and reports[key]["official_report_url"] != url:
                raise ValueError(f"Conflicting archive entries: {key}")
            reports[key] = report
    if not reports:
        raise ValueError("Archive contains no SSC reports; inspect its table before updating")
    return sorted(reports.values(), key=lambda r: (r["year"], MONTHS.index(r["month"])))


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname == "npfmc.org" or
                                         (parsed.hostname or "").endswith(".npfmc.org")):
        raise ValueError("Report URL must use HTTPS on an NPFMC host")


def fetch(url):
    validate_url(url)
    # System curl uses the OS trust store, including on macOS Python installations.
    proc = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                           "--proto", "=https", "--proto-redir", "=https",
                           "--retry", "2", "--max-time", "90", url], capture_output=True)
    if proc.returncode:
        raise ValueError(proc.stderr.decode("utf-8", errors="replace").strip())
    return proc.stdout


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-year", type=int, default=2000)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--archive-html", type=Path, help="Saved official archive for offline discovery")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    html = args.archive_html.read_text() if args.archive_html else fetch(ARCHIVE).decode("utf-8")
    reports = discover(html, args.since_year, args.as_of)
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"reports": []}
    prior = {r["source_file"]: r for r in previous["reports"]}
    existing = {}
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        if pdf.name in EXCLUDED_FILES:
            continue
        year, month = report_date(pdf.stem, "")
        if not year or not month:
            year, month = report_date(pdf.stem, "\n".join(extract_pages(pdf)[:2]))
        key = (year, month_name(month))
        if key in existing:
            raise ValueError(f"Duplicate local reports for {key}; review before importing")
        existing[key] = pdf
    saved = []
    failures = []
    added = 0
    for report in reports:
        key = (report["year"], report["month"])
        pdf = existing.get(key, PDF_DIR / f"SSC {report['month']} {report['year']}.pdf")
        report["source_file"] = pdf.name
        if args.dry_run:
            print("KEEP" if pdf.exists() else "ADD", pdf.name, flush=True)
            continue
        try:
            if not pdf.exists():
                data = fetch(report["official_report_url"])
                if not data.startswith(b"%PDF-"):
                    raise ValueError("Download is not a PDF")
                temp = pdf.with_suffix(".part.pdf")
                try:
                    temp.write_bytes(data)
                    pages = extract_pages(temp)
                    title = " ".join(pages[:2])
                    scanned = sum(len(page.strip()) for page in pages) < 100
                    if scanned:
                        print("OCR", pdf.name, flush=True)
                        pages = ocr_pages(temp)
                        title = " ".join(pages[:2])
                    if not re.search(r"\bSSC\b|Scientific\s+(?:and\s+)?Statistical", title, re.I):
                        raise ValueError("PDF title does not identify the SSC")
                    if scanned:
                        sidecar = ROOT / "data" / "ocr" / f"{pdf.name}.json"
                        sidecar.parent.mkdir(parents=True, exist_ok=True)
                        sidecar.write_text(json.dumps({"pdf_sha256": digest(temp), "method": "tesseract-eng-200dpi",
                                                      "review_status": "machine OCR; verify against PDF", "pages": pages}, indent=2) + "\n")
                    temp.replace(pdf)
                finally:
                    temp.unlink(missing_ok=True)
                added += 1
                report["download_url"] = report["official_report_url"]
                report["downloaded_on"] = args.as_of.isoformat()
                print("ADDED", pdf.name, flush=True)
            else:
                # Retained PDFs may be an earlier edition than the current archive link.
                for field in ("download_url", "downloaded_on"):
                    if field in prior.get(pdf.name, {}):
                        report[field] = prior[pdf.name][field]
            report["sha256"] = digest(pdf)
            report["pages"] = len(extract_pages(pdf))
            report["text_method"] = "OCR (verify against PDF)" if (ROOT / "data" / "ocr" / f"{pdf.name}.json").exists() else "PDF text"
            report["provenance"] = "downloaded" if "download_url" in report else "retained local edition"
            saved.append(report)
        except Exception as error:
            failures.append({**report, "error": str(error)})
            print("FAILED", pdf.name, str(error), flush=True)
    if args.dry_run:
        print(f"Discovered {len(reports)} SSC reports")
        return
    known = {r["source_file"] for r in saved}
    for pdf in existing.values():
        if pdf.name not in known:
            year, month = report_date(pdf.stem, "\n".join(extract_pages(pdf)[:2]))
            saved.append({**prior.get(pdf.name, {}), "source_file": pdf.name, "year": year, "month": month_name(month),
                          "sha256": digest(pdf), "pages": len(extract_pages(pdf)),
                          "provenance": prior.get(pdf.name, {}).get("provenance", "retained local edition")})
    manifest = {"archive_url": ARCHIVE, "checked_on": args.as_of.isoformat(),
                "since_year": args.since_year, "discovered_reports": len(reports),
                "excluded_files": EXCLUDED_FILES, "failures": failures,
                "reports": sorted(saved, key=lambda r: (r["year"], MONTHS.index(r["month"]) if r["month"] else -1))}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Added {added}; available {len(saved)}; failed {len(failures)}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
