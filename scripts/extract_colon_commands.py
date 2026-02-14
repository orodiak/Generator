#!/usr/bin/env python3
"""Extract colon-containing tokens from a PDF manual and show context.

Usage: python scripts/extract_colon_commands.py /path/to/manual.pdf
"""
import sys
from pathlib import Path
from PyPDF2 import PdfReader
import re

def extract(path: Path):
    reader = PdfReader(str(path))
    commands = {}
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        up = text.replace('\r','\n')
        # find tokens containing colon and letters/numbers/:?*=.-
        tokens = re.findall(r"[A-Z0-9\-_*\.:\?=]{2,}", up.upper())
        for tok in tokens:
            if ':' in tok:
                # store a snippet: full line(s) containing token
                for line in up.splitlines():
                    if tok in line.upper():
                        commands.setdefault(tok, set()).add((i, line.strip()))
    return commands


def main():
    if len(sys.argv) < 2:
        print('Usage: extract_colon_commands.py /path/to/manual.pdf')
        sys.exit(2)
    pdf = Path(sys.argv[1])
    if not pdf.exists():
        print('File not found:', pdf)
        sys.exit(1)
    cmds = extract(pdf)
    out = Path('docs') / 'manual_colon_commands.txt'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8') as f:
        for tok in sorted(cmds.keys()):
            f.write(f'COMMAND: {tok}\n')
            for page, line in sorted(cmds[tok]):
                f.write(f'  Page {page}: {line}\n')
            f.write('\n')
    print(f'Found {len(cmds)} unique colon-commands; written to {out}')

if __name__ == '__main__':
    main()
