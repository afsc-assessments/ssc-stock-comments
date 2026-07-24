# SSC Stock Comments

This repository is a page-aware database and lightweight web UI for searching North Pacific Council SSC report comments by stock, FMP, year, and comment type.

## Contents

- `data/processed/ssc_stock_comments.csv`: page-aware comment records for analysis.
- `data/processed/ssc_stock_summary.csv`: stock/FMP summary counts.
- `docs/`: static web UI suitable for local use or GitHub Pages.
- `docs/pdfs/`: the unique source SSC report PDFs served by the web UI.
- `scripts/build_data.py`: reproducible data builder using `pdftotext`.

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
- `model_choice_flag`: `true` only when the text explicitly indicates that the SSC
  selected a different model.
- `model_choice_confidence`: `high` for explicit same-paragraph classifications or
  `review` when surrounding text suggests a comparison that requires verification.
- `model_choice_evidence`: the source sentence supporting the classification.
- `excerpt`: card-friendly text.
- `full_text`: full source paragraph.

The extraction is intentionally auditable. Broad ecosystem paragraphs may match multiple stocks when they discuss several species; use `matched_terms`, `section`, `source_file`, and `page` during curation.

Human-reviewed model-choice classifications can be added to
`data/model_choice_overrides.csv`. Overrides are keyed by source file, page,
paragraph index, and stock, and are applied whenever the data are rebuilt.
