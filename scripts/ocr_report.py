"""Recognize scanned report pages without changing the source PDF."""

import subprocess
import tempfile
from pathlib import Path


def ocr_pages(pdf):
    with tempfile.TemporaryDirectory(prefix="ssc-ocr-") as temp:
        directory = Path(temp).resolve()
        subprocess.run(["pdftoppm", "-r", "200", "-png", str(pdf.resolve()),
                        str(directory / "page")], check=True, capture_output=True)
        images = sorted(directory.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
        pages = []
        for image in images:
            result = subprocess.run(["tesseract", str(image), "stdout", "-l", "eng"],
                                    check=True, capture_output=True, text=True)
            pages.append(result.stdout)
        if not pages:
            raise ValueError("OCR produced no pages")
        return pages
