#!/usr/bin/env python3
"""Extract relevant SCPI command examples from a PDF manual.

Usage: python scripts/parse_manual.py /path/to/manual.pdf

Prints lines/pages that mention the keywords and writes a summary to
`docs/manual_scpi_snippets.txt` in the workspace.
"""
import sys
from pathlib import Path
from PyPDF2 import PdfReader

KEYWORDS = [
    "FREQ", "SOUR:FREQ", "POW", "SOUR:POW", "OUTP", "MOD", "FM",
    "LFO", "SYST:ERR", "SYST:ERR?", "SYST:ERR?", "SYST:ERR?", "*CLS",
    "*IDN?", "FREQ?", "POW?", "MOD:FM:DEV", "MOD:TYPE", "LFO:FREQ",
]

def search_pdf(path: Path):
    reader = PdfReader(str(path))
    matches = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        up = text.upper()
        for kw in KEYWORDS:
            if kw in up:
                # capture snippet around keyword occurrences
                for line in up.splitlines():
                    if kw in line:
                        matches.append((i, kw, line.strip()))
    return matches


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_manual.py /path/to/manual.pdf")
        sys.exit(2)
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    matches = search_pdf(pdf_path)
    out_file = Path(__file__).resolve().parents[1] / 'docs' / 'manual_scpi_snippets.txt'
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open('w', encoding='utf-8') as f:
        if not matches:
            f.write('No SCPI-like keywords found.\n')
            print('No matches found.')
            return
        for page, kw, line in matches:
            f.write(f'Page {page}: {kw} -> {line}\n')
    print(f'Found {len(matches)} matches; written to {out_file}')

if __name__ == '__main__':
    main()
