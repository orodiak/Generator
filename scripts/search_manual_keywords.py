#!/usr/bin/env python3
"""Search PDF manual for control-related keywords and save context lines.

Usage: python scripts/search_manual_keywords.py /path/to/manual.pdf
"""
import sys
from pathlib import Path
from PyPDF2 import PdfReader
import re

KEYWORDS = [r"\bRF\b", r"\bLEVEL\b", r"\bFREQ\b", r"\bPOW\b", r"\bFM\b", r"FM:INT", r"\bAF\b", r"SYST:ERR\?", r"\*ESR\?", r"ERRORS?", r"ERR\b"]


def search_pdf(path: Path):
    reader = PdfReader(str(path))
    matches = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        lines = text.splitlines()
        for ln_idx, line in enumerate(lines):
            upper = line.upper()
            for kw in KEYWORDS:
                if re.search(kw, upper):
                    # capture a small context of +/-1 lines
                    context_lines = []
                    for j in range(max(0, ln_idx-1), min(len(lines), ln_idx+2)):
                        context_lines.append(lines[j].strip())
                    matches.append((i, kw, " \\n".join(context_lines)))
                    break
    return matches


def main():
    if len(sys.argv) < 2:
        print("Usage: search_manual_keywords.py /path/to/manual.pdf")
        sys.exit(2)
    pdf = Path(sys.argv[1])
    if not pdf.exists():
        print('File not found:', pdf)
        sys.exit(1)
    matches = search_pdf(pdf)
    out = Path('docs') / 'manual_keyword_snippets.txt'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8') as f:
        if not matches:
            f.write('No matches found.\n')
            print('No matches found.')
            return
        for page, kw, ctx in matches:
            f.write(f'Page {page} | {kw} | {ctx}\n---\n')
    print(f'Found {len(matches)} matches; written to {out}')

if __name__ == '__main__':
    main()
