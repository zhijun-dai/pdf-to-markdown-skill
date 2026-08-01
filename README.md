# pdf-to-markdown-skill

A Claude Code skill that converts text-based PDFs (lecture slides, textbook chapters, papers, reports) into a clean, AI-friendly Markdown document — with images extracted, scan-like pages detected and flagged, and a conversion report up front so the reader knows exactly what may be missing.

The point: after conversion you read the `.md`, never the PDF again.

## Features

- **Markdown or HTML output** (`-f md|html|both`) — tables, headings, lists preserved
- **Image extraction** — embedded images saved to `assets/`, referenced via relative paths (portable folder)
- **Scan-page detection** — pure-image pages (no text layer) are detected and flagged in the report, so you know where content is missing (no OCR)
- **Conversion report** — prepended to the output: scan-like pages, blank pages, dense-math pages (formulas extract poorly), and broken font mappings (`(cid:` glyphs)
- **Machine-readable results** — `scan_report.json` for tooling

## Usage

```bash
pip install pymupdf4llm
python scripts/pdf2md.py <input.pdf> [-o <outdir>] [-f md|html|both]
```

Output:

```
<outdir>/
├── <basename>.md        ← Markdown with a conversion report header
├── <basename>.html      ← (if -f html|both)
├── assets/              ← extracted images
└── scan_report.json     ← scan detection results
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `-o, --outdir` | `<pdf basename>/` | Output directory |
| `-f, --format` | `md` | `md`, `html`, or `both` |
| `--image-format` | `png` | `png` or `jpg` |
| `--scan-threshold` | `30` | Max chars/page before flagging as scan/blank |
| `--no-scan-check` | off | Skip scan-page detection |

## Example

See [`examples/example-output.md`](examples/example-output.md) — a real conversion of a 65-page Chinese probability-statistics lecture deck (with its extracted images in `examples/assets/`). The formula-dense warning in the header is typical for slides with math.

## Example report header

```markdown
<!-- ===== conversion report ===== -->
input: lecture12.pdf
pages: 65
images: 5

> ⚠️ Page 12: looks like a pure-image page (0 chars, 1 images) — no text layer extracted. Check assets/ or OCR it separately.
> ⚠️ Pages 3, 7-60: dense math — formulas extract poorly (one symbol per line). Verify manually if formulas matter.
<!-- ===== end report ===== -->
```

## How it works

1. **Detect**: per-page text density via PyMuPDF — few chars + images → scan-like; few chars, no images → blank.
2. **Convert**: [pymupdf4llm](https://github.com/pymupdf/RAG) handles headings, lists, tables, and image extraction.
3. **Annotate**: prepend the report; relativize image paths so the output folder is portable.

## Limitations

- **No OCR.** Scanned pages are flagged, not transcribed.
- Formulas extract one symbol per line (inherent to PDF text extraction).
- Table fidelity depends on the source PDF's structure.
- Garbled ordering on PDFs with broken text layers (PPT exports, some translated documents) is a source-file issue, not fixable here.

## Install as a Claude Code skill

```bash
git clone https://github.com/zhijun-dai/pdf-to-markdown-skill
# copy or symlink the folder into your skills directory, e.g.:
#   C:\Users\<you>\.claude\skills\pdf-to-markdown
```

## License

MIT
