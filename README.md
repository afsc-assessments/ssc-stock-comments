# SSC Stock Comments

This repository is a page-aware database and lightweight web UI for searching North Pacific Council SSC report comments by stock, FMP, year, and comment type.

## Contents

- `data/processed/ssc_stock_comments.csv`: page-aware comment records for analysis.
- `data/processed/ssc_stock_summary.csv`: stock/FMP summary counts.
- `docs/`: static web UI suitable for local use or GitHub Pages.
- `docs/pdfs/`: the unique source SSC report PDFs served by the web UI.
- `scripts/build_data.py`: reproducible data builder using `pdftotext`.
- `scripts/sync_reports.py`: repeatable scraper of the SSC column in the official Council Records archive.
- `data/report_sources.json`: report inventory, source links, PDF hashes, dates, exclusions, and import failures.
- `data/ocr/`: source-hash-checked text for scanned PDFs; the original PDFs remain unchanged.

## Use The UI Locally

You can open `docs/index.html` directly in a browser. The repository includes `docs/assets/comments-data.js` so local `file://` use does not depend on browser permission to fetch JSON files.

From the repository root:

```sh
python3 -m http.server 8000 --directory docs
```

Then open:

```text
http://localhost:8000
```

The `Open page` links point to `docs/pdfs/<report>.pdf#page=<n>`, which opens the source PDF near the paragraph page.

The UI links to the separate ABC/TAC app at <https://jimianelli.github.io/ABC_TAC/> for ABC and OFL recommendation tables.

## Publish On GitHub Pages

This repository is configured for public GitHub Pages deployment with `.github/workflows/pages.yml`. After pushing the repository to GitHub, set the repository Pages source to **GitHub Actions** under Settings -> Pages. Each push to `main` will publish the static app from `docs/`.

The public URL will be:

```text
https://<github-user-or-org>.github.io/ssc-stock-comments/
```

If the repository is renamed, replace `ssc-stock-comments` in the URL with the GitHub repository name.

## Rebuild The Data

Refresh the NPFMC archive and then rebuild:

```sh
python3 scripts/sync_reports.py --as-of 2026-09-30
python3 scripts/build_data.py
python3 -m unittest discover -s tests -v
python3 scripts/validate_data.py
```

Omit `--as-of` to use today's date. The default archive scope starts in 2000.
Use `--dry-run` to inspect missing reports without downloading or changing the inventory.
The importer uses system `curl` with HTTPS certificate verification. Poppler and
Tesseract are needed for text extraction and scanned reports (`brew install poppler tesseract`).
It imports only the SSC report column, deduplicates meeting dates, and fails on
conflicting archive links or invalid downloads. Existing local editions are retained
so human paragraph reviews remain aligned; an official archive link can refer to a
newer edition. `download_url` records exact provenance for newly imported reports.
Import failures remain visible in the inventory and UI; they do not erase existing reports.

`SSC Dec 2024x.pdf` remains excluded. The old Pacific Council September 2016
report is also excluded from the NPFMC database; its existing file is preserved.
OCR text is machine-recognized and requires verification against the PDF.
Stock and FMP assignments remain rule-based search aids rather than a fully
curated set of recommendations. GOA Tanner crab bycatch discussions and Pribilof
golden king crab are separated from EBS Tanner crab and Aleutian golden king crab.

Install Poppler if `pdftotext` is missing. On macOS with Homebrew:

```sh
brew install poppler
```

Then run:

```sh
python3 scripts/build_data.py
```

The script rebuilds `data/processed/*.csv`, `docs/assets/comments.json`, and `docs/assets/comments-data.js`.

## Data Fields

- `stock`: normalized stock or stock complex.
- `fmp`: `BSAI`, `GOA`, or `BSAI/GOA`.
- `comment_type`: rule-based category such as `request`, `recommendation`, `support/concur`, or `concern`. The UI's comment type filter also includes ABC term flags from `abc_buffer_terms`: `maximum permissible`, `buffer`, `reduction`, and `from maxABC`.
- `year`, `month`, `source_file`, `page`: source metadata.
- `page_url`: UI-ready link to the PDF page.
- `abc_buffer_terms`: matched terminology for ABC buffers or reductions from maximum permissible ABC.
- `model_choice_relationship`: SSC agreement or disagreement with the assessment
  authors and/or Plan Team on model selection. Ambiguous candidates are `unclear`.
- `model_choice_flag`: `true` for explicit different-model cases and candidates
  marked for review.
- `model_choice_confidence`: `high` for explicit same-paragraph classifications or
  `review` when surrounding text suggests a comparison that requires verification.
- `model_choice_evidence`: the source sentence supporting the classification.
- `excerpt`: card-friendly text.
- `full_text`: full source paragraph.

The extraction is intentionally auditable. Broad ecosystem paragraphs may match multiple stocks when they discuss several species; use `matched_terms`, `section`, `source_file`, and `page` during curation.

Human-reviewed model-choice classifications can be added to
`data/model_choice_overrides.csv`. Overrides are keyed by source file, page,
paragraph index, and stock, and are applied whenever the data are rebuilt.

## Optional Jev Review

Jev is used as a separate model-choice review assistant, rather than for downloading
reports or extracting page locations. Prepare a 20-record pilot without API calls:

```sh
python3 scripts/review_jev.py
```

With `TYPESAFE_API_KEY` supplied locally, run `python3 scripts/review_jev.py --run`.
The implementation follows the [TypeSafe API](https://docs.typesafe.ai/api) and pins
`jev-1.13.0`. It asks separate questions for assessment authors and Plan Team
comparisons, including `no_explicit_comparison` and `unclear`. Requests are cached
by source-PDF hash, physical page, paragraph-text hash, stock, question version,
and full request content. Responses are checked for valid model, labels,
probabilities, and token accounting before reuse.

All requests, suggestions, and probabilities stay in ignored `.jev/`. Review
`.jev/review.csv` against the linked PDF page, then enter verified decisions in
`data/model_choice_overrides.csv`. Jev suggestions never overwrite rules or human
reviews automatically. The public GitHub Pages application contains no API key or
live inference dependency. Live API behavior requires a separate credentialed test.
