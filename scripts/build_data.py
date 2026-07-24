#!/usr/bin/env python3
"""Build page-aware SSC stock comment data for the static UI."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "docs" / "pdfs"
OUT = ROOT / "data" / "processed"
WEB_ASSETS = ROOT / "docs" / "assets"
MODEL_CHOICE_OVERRIDES = ROOT / "data" / "model_choice_overrides.csv"


@dataclass(frozen=True)
class Stock:
    stock: str
    fmp: str
    aliases: tuple[str, ...]


STOCKS: tuple[Stock, ...] = (
    Stock("Walleye pollock", "BSAI/GOA", ("pollock", "walleye pollock", "EBS pollock", "AI pollock", "Bogoslof pollock", "GOA pollock")),
    Stock("Pacific cod", "BSAI/GOA", ("Pacific cod", "EBS Pacific cod", "AI Pacific cod", "GOA Pacific cod", "cod stock")),
    Stock("Sablefish", "BSAI/GOA", ("sablefish", "Alaska sablefish")),
    Stock("Yellowfin sole", "BSAI", ("yellowfin sole",)),
    Stock("Greenland turbot", "BSAI/GOA", ("Greenland turbot",)),
    Stock("Arrowtooth flounder", "BSAI/GOA", ("arrowtooth flounder",)),
    Stock("Kamchatka flounder", "BSAI/GOA", ("Kamchatka flounder",)),
    Stock("Northern rock sole", "BSAI/GOA", ("northern rock sole",)),
    Stock("Southern rock sole", "GOA", ("southern rock sole",)),
    Stock("Flathead sole", "BSAI/GOA", ("flathead sole",)),
    Stock("Alaska plaice", "BSAI", ("Alaska plaice",)),
    Stock("Other flatfish", "BSAI", ("other flatfish",)),
    Stock("Deepwater flatfish", "GOA", ("deepwater flatfish", "Dover sole", "deepsea sole")),
    Stock("Shallow-water flatfish", "GOA", ("shallow-water flatfish", "shallow water flatfish")),
    Stock("Rex sole", "GOA", ("rex sole",)),
    Stock("Pacific ocean perch", "BSAI/GOA", ("Pacific ocean perch", "POP")),
    Stock("Northern rockfish", "BSAI/GOA", ("northern rockfish",)),
    Stock("Dusky rockfish", "GOA", ("dusky rockfish",)),
    Stock("Rougheye/blackspotted rockfish", "BSAI/GOA", ("rougheye", "blackspotted", "RE/BS", "BS/RE")),
    Stock("Shortraker rockfish", "BSAI/GOA", ("shortraker rockfish",)),
    Stock("Other rockfish", "BSAI/GOA", ("other rockfish",)),
    Stock("Demersal shelf rockfish", "GOA", ("demersal shelf rockfish", "DSR", "yelloweye rockfish")),
    Stock("Thornyhead rockfish", "GOA", ("thornyhead", "thornyhead rockfish")),
    Stock("Atka mackerel", "BSAI/GOA", ("Atka mackerel",)),
    Stock("Skates", "BSAI/GOA", ("skate", "skates", "Alaska skate", "big skate", "longnose skate")),
    Stock("Sharks", "BSAI/GOA", ("shark", "sharks")),
    Stock("Octopuses", "BSAI", ("octopus", "octopuses")),
    Stock("Squids", "BSAI/GOA", ("squid", "squids")),
    Stock("Forage fish", "BSAI/GOA", ("forage fish", "forage species")),
    Stock("Grenadiers", "BSAI/GOA", ("grenadier", "grenadiers")),
    Stock("EBS snow crab", "BSAI", ("snow crab", "EBS snow crab")),
    Stock("Bristol Bay red king crab", "BSAI", ("Bristol Bay red king crab", "BB red king crab")),
    Stock("EBS Tanner crab", "BSAI", ("Tanner crab", "EBS Tanner crab")),
    Stock("Pribilof Islands red king crab", "BSAI", ("Pribilof Islands red king crab",)),
    Stock("Pribilof Islands blue king crab", "BSAI", ("Pribilof Islands blue king crab",)),
    Stock("St. Matthew Island blue king crab", "BSAI", ("St. Matthew", "St Matthew", "blue king crab")),
    Stock("Norton Sound red king crab", "BSAI", ("Norton Sound red king crab", "NSRKC")),
    Stock("Aleutian Islands golden king crab", "BSAI", ("golden king crab", "AI golden king crab")),
    Stock("Western Aleutian Islands red king crab", "BSAI", ("Western AI red king crab", "Western Aleutian Islands red king crab")),
    Stock("Scallops", "BSAI/GOA", ("scallop", "scallops")),
    Stock("Salmon", "BSAI/GOA", ("salmon", "chum salmon", "Chinook salmon", "pink salmon", "sockeye salmon")),
    Stock("Halibut", "BSAI/GOA", ("halibut",)),
    Stock("Herring", "BSAI/GOA", ("herring", "Togiak herring")),
)


ACTION_PATTERNS = {
    "request": re.compile(r"\bSSC\s+(requests?|asked|recommended that)\b", re.I),
    "recommendation": re.compile(r"\bSSC\s+(recommends?|recommended)\b", re.I),
    "support/concur": re.compile(r"\bSSC\s+(supports?|supported|concurs?|concurred|agrees?|agreed|endorses?)\b", re.I),
    "concern": re.compile(r"\bSSC\s+(is concerned|expressed concern|notes? .*concern|highlights?)\b", re.I),
    "appreciation": re.compile(r"\bSSC\s+(thanks?|appreciates?|commended|commends?)\b", re.I),
    "note": re.compile(r"\bSSC\s+(notes?|recognizes?|acknowledges?|reiterates?|suggests?|encourages?)\b", re.I),
}


ABC_BUFFER_PATTERNS = {
    "maximum permissible ABC": re.compile(
        r"\b(?:maximum|max)\s+permissible(?:\s+(?:ABC|levels?))?\b|\bmax\s*ABC\b",
        re.I,
    ),
    "ABC buffer": re.compile(
        r"\b(?:ABCs?|FABC|max\s*ABC|maximum permissible)\b.{0,90}\b(?:buffer|buffers|buffered)\b"
        r"|\b(?:buffer|buffers|buffered)\b.{0,90}\b(?:ABCs?|FABC|max\s*ABC|maximum permissible)\b",
        re.I,
    ),
    "ABC reduction": re.compile(
        r"\b(?:ABCs?|FABC|max\s*ABC|maximum permissible)\b.{0,90}\b(?:reduction|reduced|reduce|lower|below|less than)\b"
        r"|\b(?:reduction|reduced|reduce|lower|below|less than)\b.{0,90}\b(?:ABCs?|FABC|max\s*ABC|maximum permissible)\b",
        re.I,
    ),
    "from maxABC": re.compile(
        r"\bfrom\s+(?:the\s+)?(?:max\s*ABC|maximum permissible(?:\s+ABC)?)\b",
        re.I,
    ),
}

MODEL_CHOICE_RELATIONSHIPS = (
    "different_from_both",
    "different_from_plan_team",
    "different_from_authors",
    "agrees_with_both",
    "agrees_with_plan_team",
    "agrees_with_authors",
    "unclear",
)

MODEL_LANGUAGE = re.compile(
    r"\b(?:model(?:s|ing)?|alternative(?:s)?|configuration(?:s)?|base case|reference case)\b",
    re.I,
)
MODEL_SELECTION_LANGUAGE = re.compile(
    r"\b(?:select(?:s|ed|ion)?|cho(?:ose|oses|se|sen)|prefer(?:s|red|ence)?|"
    r"recommend(?:s|ed|ation)?|adopt(?:s|ed|ion)?|accept(?:s|ed|ance)?|"
    r"support(?:s|ed)?|agree(?:s|d)?|concur(?:s|red)?|disagree(?:s|d)?|"
    r"instead|rather than|bring(?:ing)? forward|use|using)\b",
    re.I,
)
PLAN_TEAM_LANGUAGE = re.compile(r"\b(?:Plan Team|[BG]PT|CPT|team)\b", re.I)
AUTHOR_LANGUAGE = re.compile(r"\b(?:assessment )?author(?:s|'s|s')?\b", re.I)
SSC_LANGUAGE = re.compile(r"\bSSC\b", re.I)
CONTRAST_LANGUAGE = re.compile(
    r"\b(?:disagree(?:s|d)?|did not agree|does not support|did not support|"
    r"instead|rather than|different (?:model|alternative)|"
    r"depart(?:s|ed|ure)? from)\b",
    re.I,
)
AGREEMENT_LANGUAGE = re.compile(
    r"\b(?:agree(?:s|d)? with|concur(?:s|red)? with|support(?:s|ed)?|"
    r"endorse(?:s|d)?|recommend(?:s|ed)? (?:the )?(?:author|Plan Team|[BG]PT|CPT))\b",
    re.I,
)
EXPLICIT_MODEL_DIFFERENCE = re.compile(
    r"(?:"
    r"\bSSC\b.{0,180}\b(?:disagree(?:s|d)? with|did not (?:agree with|support)|"
    r"does not support)\b.{0,180}\b(?:Plan Team|[BG]PT|CPT|(?:assessment )?authors?)\b"
    r".{0,180}\bmodel\b"
    r"|"
    r"\bSSC\b.{0,180}\b(?:select(?:s|ed)?|cho(?:ose|oses|se)|prefer(?:s|red)?|"
    r"recommend(?:s|ed)?|adopt(?:s|ed)?)\b.{0,180}\bmodel\b.{0,180}"
    r"\b(?:instead of|rather than)\b.{0,180}"
    r"\b(?:Plan Team|[BG]PT|CPT|(?:assessment )?authors?)\b"
    r")",
    re.I,
)


COMMENT_TYPE_BUFFER_FILTERS = {
    "maximum permissible": "maximum permissible ABC",
    "buffer": "ABC buffer",
    "reduction": "ABC reduction",
    "from maxABC": "from maxABC",
}


def normalize_ws(text: str) -> str:
    text = re.sub(r"-\n\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if re.match(r"^\d+\s+of\s+\d+\b", stripped):
            continue
        if re.match(r"^SSC Report.*(?:Council|Draft)", stripped, re.I):
            continue
        if re.match(r"^(December|October|June|September)\s+\d{4}$", stripped):
            continue
        lines.append(line.rstrip())
    return lines


def extract_pages(pdf: Path) -> list[str]:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    )
    pages = proc.stdout.split("\f")
    return [page for page in pages if page.strip()]


def report_pages(pdf: Path) -> tuple[list[str], list[dict[str, str | int]]]:
    pages = extract_pages(pdf)
    return pages, paragraphs_by_page(pages)


def paragraphs_by_page(pages: list[str]) -> list[dict[str, str | int]]:
    blocks: list[dict[str, str | int]] = []
    for page_number, page in enumerate(pages, start=1):
        current: list[str] = []
        for line in clean_lines(page):
            if line.strip():
                current.append(line)
            elif current:
                text = normalize_ws("\n".join(current))
                if len(text) > 20:
                    blocks.append({"page": page_number, "text": text})
                current = []
        if current:
            text = normalize_ws("\n".join(current))
            if len(text) > 20:
                blocks.append({"page": page_number, "text": text})
    return blocks


def report_date(name: str, text: str) -> tuple[str, str]:
    year_match = re.search(r"(20\d{2}|19\d{2})", name) or re.search(r"\b(20\d{2}|19\d{2})\b", text[:2000])
    month_match = re.search(r"\b(Dec|December|Oct|October|June|Sept|September)\b", name, re.I)
    if not month_match:
        month_match = re.search(r"\b(December|October|June|September|February|April)\b", text[:2000], re.I)
    return (year_match.group(1) if year_match else "", month_match.group(1) if month_match else "")


def update_context(para: str, current: str) -> str:
    if re.search(r"\bBSAI\b.*\bGOA\b|\bGOA\b.*\bBSAI\b", para):
        return "BSAI/GOA"
    if re.search(r"\b(BSAI|Bering Sea|Aleutian Islands|EBS)\b", para):
        return "BSAI"
    if re.search(r"\b(GOA|Gulf of Alaska)\b", para):
        return "GOA"
    return current


def infer_fmp(stock: Stock, para: str, context_fmp: str) -> str:
    if stock.fmp != "BSAI/GOA":
        return stock.fmp
    has_bsai = bool(re.search(r"\b(BSAI|Bering Sea|Aleutian Islands|EBS|AI)\b", para))
    has_goa = bool(re.search(r"\b(GOA|Gulf of Alaska)\b", para))
    if has_bsai and has_goa:
        return "BSAI/GOA"
    if has_bsai:
        return "BSAI"
    if has_goa:
        return "GOA"
    if context_fmp:
        return context_fmp
    if re.search(r"\b(bogoslof|ebs)\b", para, re.I):
        return "BSAI"
    return stock.fmp


def section_label(para: str, previous: str) -> str:
    if len(para) <= 140 and (
        re.match(r"^[A-Z]\d+\b", para)
        or re.search(r"\b(SAFE|Specifications|Groundfish|Crab|Ecosystem Status|Rockfish|Flatfish)\b", para)
    ):
        return para
    return previous


def stock_matches(para: str) -> list[tuple[Stock, str]]:
    matches: list[tuple[Stock, str]] = []
    for stock in STOCKS:
        found: list[str] = []
        for alias in stock.aliases:
            flags = 0 if alias.isupper() else re.I
            if re.search(rf"(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])", para, flags):
                found.append(alias)
        if found:
            matches.append((stock, "; ".join(sorted(set(found), key=str.lower))))
    return matches


def comment_type(para: str) -> str:
    for name, pattern in ACTION_PATTERNS.items():
        if pattern.search(para):
            return name
    if "SSC" in para:
        return "ssc_comment"
    return "context"


def abc_buffer_terms(para: str) -> str:
    matches = [name for name, pattern in ABC_BUFFER_PATTERNS.items() if pattern.search(para)]
    return "; ".join(matches)


def evidence_sentence(text: str) -> str:
    """Return the shortest sentence that documents the model-choice relationship."""
    sentences = re.split(r"(?<=[.!?])\s+", normalize_ws(text))
    candidates = [
        sentence
        for sentence in sentences
        if SSC_LANGUAGE.search(sentence)
        and MODEL_LANGUAGE.search(sentence)
        and (CONTRAST_LANGUAGE.search(sentence) or AGREEMENT_LANGUAGE.search(sentence))
    ]
    if not candidates:
        candidates = [
            sentence
            for sentence in sentences
            if MODEL_LANGUAGE.search(sentence)
            and MODEL_SELECTION_LANGUAGE.search(sentence)
            and (PLAN_TEAM_LANGUAGE.search(sentence) or AUTHOR_LANGUAGE.search(sentence))
        ]
    return min(candidates, key=len)[:700] if candidates else ""


def model_choice_relationship(
    para: str,
    adjacent_text: str = "",
) -> dict[str, str | bool]:
    """Classify explicit SSC model-choice comparisons without inferring outcomes."""
    base = normalize_ws(para)
    result: dict[str, str | bool] = {
        "model_choice_relationship": "",
        "model_choice_flag": False,
        "model_choice_confidence": "",
        "model_choice_evidence": "",
    }
    if not (SSC_LANGUAGE.search(base) and MODEL_LANGUAGE.search(base)):
        return result

    sentences = re.split(r"(?<=[.!?])\s+", base)
    explicit_sentences = [
        sentence
        for sentence in sentences
        if SSC_LANGUAGE.search(sentence)
        and MODEL_LANGUAGE.search(sentence)
        and MODEL_SELECTION_LANGUAGE.search(sentence)
        and (PLAN_TEAM_LANGUAGE.search(sentence) or AUTHOR_LANGUAGE.search(sentence))
    ]
    explicit_text = " ".join(explicit_sentences)
    has_team = bool(PLAN_TEAM_LANGUAGE.search(explicit_text))
    has_author = bool(AUTHOR_LANGUAGE.search(explicit_text))
    has_selection = bool(MODEL_SELECTION_LANGUAGE.search(explicit_text))
    has_contrast = bool(EXPLICIT_MODEL_DIFFERENCE.search(explicit_text))
    has_agreement = bool(AGREEMENT_LANGUAGE.search(explicit_text))
    evidence = evidence_sentence(base)

    # A confirmed difference requires model language, a named comparison party,
    # and contrast/selection language in the same extracted paragraph.
    if has_selection and has_contrast and (has_team or has_author):
        if has_team and has_author:
            relationship = "different_from_both"
        elif has_team:
            relationship = "different_from_plan_team"
        else:
            relationship = "different_from_authors"
        result.update(
            {
                "model_choice_relationship": relationship,
                "model_choice_flag": True,
                "model_choice_confidence": "high",
                "model_choice_evidence": evidence or base[:700],
            }
        )
        return result

    if has_selection and has_agreement and (has_team or has_author):
        if has_team and has_author:
            relationship = "agrees_with_both"
        elif has_team:
            relationship = "agrees_with_plan_team"
        else:
            relationship = "agrees_with_authors"
        result.update(
            {
                "model_choice_relationship": relationship,
                "model_choice_confidence": "high",
                "model_choice_evidence": evidence or base[:700],
            }
        )
        return result

    # Adjacent paragraphs are useful for finding candidates, but are not safe
    # enough to assert that the SSC actually selected a different model.
    window = normalize_ws(f"{adjacent_text} {base}")
    review_sentences = re.split(r"(?<=[.!?])\s+", window)
    has_review_comparison = any(
        MODEL_LANGUAGE.search(sentence)
        and MODEL_SELECTION_LANGUAGE.search(sentence)
        and CONTRAST_LANGUAGE.search(sentence)
        and (PLAN_TEAM_LANGUAGE.search(sentence) or AUTHOR_LANGUAGE.search(sentence))
        for sentence in review_sentences
    )
    if (
        SSC_LANGUAGE.search(window)
        and has_review_comparison
        and (PLAN_TEAM_LANGUAGE.search(window) or AUTHOR_LANGUAGE.search(window))
    ):
        result.update(
            {
                "model_choice_relationship": "unclear",
                "model_choice_flag": True,
                "model_choice_confidence": "review",
                "model_choice_evidence": evidence_sentence(window) or base[:700],
            }
        )
    return result


def load_model_choice_overrides() -> dict[tuple[str, int, int, str], dict[str, str | bool]]:
    """Load human-reviewed classifications keyed to a source paragraph and stock."""
    overrides: dict[tuple[str, int, int, str], dict[str, str | bool]] = {}
    if not MODEL_CHOICE_OVERRIDES.exists():
        return overrides
    with MODEL_CHOICE_OVERRIDES.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            relationship = row["model_choice_relationship"].strip()
            if relationship not in MODEL_CHOICE_RELATIONSHIPS:
                raise ValueError(f"Invalid model-choice relationship: {relationship}")
            key = (
                row["source_file"].strip(),
                int(row["page"]),
                int(row["paragraph_index"]),
                row["stock"].strip(),
            )
            overrides[key] = {
                "model_choice_relationship": relationship,
                "model_choice_flag": (
                    relationship.startswith("different_from_")
                    or row["model_choice_confidence"].strip() == "review"
                ),
                "model_choice_confidence": row["model_choice_confidence"].strip() or "high",
                "model_choice_evidence": row["model_choice_evidence"].strip(),
            }
    return overrides


def comment_type_filters(rows: list[dict[str, str | int]]) -> list[str]:
    action_types = sorted({str(r["comment_type"]) for r in rows})
    present_buffer_types = {
        term
        for row in rows
        for term in str(row["abc_buffer_terms"]).split("; ")
        if term
    }
    buffer_types = [
        label
        for label, buffer_term in COMMENT_TYPE_BUFFER_FILTERS.items()
        if buffer_term in present_buffer_types
    ]
    return action_types + buffer_types


def make_excerpt(para: str, max_len: int = 520) -> str:
    if len(para) <= max_len:
        return para
    return para[:max_len].rsplit(" ", 1)[0] + "..."


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    WEB_ASSETS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str | int]] = []
    seen: set[tuple[str, str, str, int, str]] = set()
    model_choice_overrides = load_model_choice_overrides()

    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        pages, page_blocks = report_pages(pdf)
        whole_text = "\n".join(pages)
        year, month = report_date(pdf.stem, whole_text)
        context = ""
        section = ""
        pdf_url = f"pdfs/{quote(pdf.name)}"
        for idx, block in enumerate(page_blocks, start=1):
            para = str(block["text"])
            page = int(block["page"])
            adjacent = " ".join(
                str(page_blocks[neighbor]["text"])
                for neighbor in (idx - 2, idx)
                if 0 <= neighbor < len(page_blocks)
            )
            context = update_context(para, context)
            section = section_label(para, section)
            matches = stock_matches(para)
            if not matches:
                continue
            ctype = comment_type(para)
            buffer_terms = abc_buffer_terms(para)
            model_choice = model_choice_relationship(para, adjacent)
            if ctype == "context" and "SSC" not in para and not re.search(r"\b(assessment|SAFE|OFL|ABC|model|risk table|harvest)\b", para, re.I):
                continue
            for stock, aliases in matches:
                fmp = infer_fmp(stock, para, context)
                override_key = (pdf.name, page, idx, stock.stock)
                stock_model_choice = model_choice_overrides.get(override_key, model_choice)
                key = (pdf.name, stock.stock, fmp, page, para[:180])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": len(rows) + 1,
                        "stock": stock.stock,
                        "fmp": fmp,
                        "comment_type": ctype,
                        "year": year,
                        "month": month,
                        "source_file": pdf.name,
                        "page": page,
                        "paragraph_index": idx,
                        "section": section,
                        "matched_terms": aliases,
                        "abc_buffer_terms": buffer_terms,
                        **stock_model_choice,
                        "excerpt": make_excerpt(para),
                        "full_text": para,
                        "pdf_url": pdf_url,
                        "page_url": f"{pdf_url}#page={page}",
                    }
                )

    fieldnames = [
        "id",
        "stock",
        "fmp",
        "comment_type",
        "year",
        "month",
        "source_file",
        "page",
        "paragraph_index",
        "section",
        "matched_terms",
        "abc_buffer_terms",
        "model_choice_relationship",
        "model_choice_flag",
        "model_choice_confidence",
        "model_choice_evidence",
        "excerpt",
        "full_text",
        "pdf_url",
        "page_url",
    ]
    with (OUT / "ssc_stock_comments.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "records": rows,
        "filters": {
            "stocks": sorted({str(r["stock"]) for r in rows}),
            "years": sorted({str(r["year"]) for r in rows if r["year"]}),
            "fmps": ["BSAI", "GOA", "BSAI/GOA"],
            "comment_types": comment_type_filters(rows),
            "model_choice_relationships": [
                relationship
                for relationship in MODEL_CHOICE_RELATIONSHIPS
                if any(r["model_choice_relationship"] == relationship for r in rows)
            ],
        },
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    (WEB_ASSETS / "comments.json").write_text(payload_json, encoding="utf-8")
    (WEB_ASSETS / "comments-data.js").write_text(
        f"window.SSC_COMMENTS_DATA = {payload_json};\n",
        encoding="utf-8",
    )

    counts = Counter((str(r["stock"]), str(r["fmp"])) for r in rows)
    years: dict[tuple[str, str], set[str]] = defaultdict(set)
    files: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_type: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        key = (str(row["stock"]), str(row["fmp"]))
        years[key].add(str(row["year"]))
        files[key].add(str(row["source_file"]))
        by_type[key][str(row["comment_type"])] += 1
    with (OUT / "ssc_stock_summary.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["stock", "fmp", "records", "years", "source_files", "comment_types"])
        writer.writeheader()
        for (stock, fmp), count in sorted(counts.items()):
            writer.writerow(
                {
                    "stock": stock,
                    "fmp": fmp,
                    "records": count,
                    "years": ";".join(sorted(years[(stock, fmp)])),
                    "source_files": len(files[(stock, fmp)]),
                    "comment_types": json.dumps(by_type[(stock, fmp)], sort_keys=True),
                }
            )

    print(f"Wrote {len(rows)} comment records from {len(list(PDF_DIR.glob('*.pdf')))} PDFs.")


if __name__ == "__main__":
    main()
