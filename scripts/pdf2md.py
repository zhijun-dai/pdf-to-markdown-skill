#!/usr/bin/env python3
"""Convert a text-based PDF into an AI-friendly Markdown (or HTML) document.

- Detects scan-like pages (little text but images) and blank pages, then
  annotates them in the output so the reader knows text is missing.
- Extracts embedded images into an assets/ folder referenced by relative paths.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pymupdf
import pymupdf4llm

SCAN_CHAR_THRESHOLD = 30
REPORT_TEMPLATE = """<!-- ===== conversion report ===== -->
input: {input}
pages: {pages}
images: {image_count}
{scan_notes}
{formula_notes}{cid_notes}
<!-- ===== end report ===== -->

"""


def detect_problem_pages(doc, threshold):
    pages = []
    for i, page in enumerate(doc, 1):
        n = len(page.get_text())
        images = len(page.get_images())
        if n < threshold:
            kind = "scan" if images else "blank"
            pages.append({"page": i, "chars": n, "images": images, "kind": kind})
    return pages


def inspect_garbage(doc, sample_pages=None):
    sample_pages = sample_pages or range(1, min(len(doc), 20) + 1)
    total = 0
    cid = 0
    for i in sample_pages:
        text = doc[i - 1].get_text()
        total += len(text)
        cid += len(re.findall(r"\(cid:", text))
    if total == 0:
        return None
    return cid / total if cid else None


def inspect_formula_pages(doc):
    # math tends to extract as one character per line (mupdf has no math layout)
    dense = []
    for i, page in enumerate(doc, 1):
        blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
        lines = [l for b in blocks for l in b["lines"]]
        if len(lines) < 20:
            continue
        short = sum(1 for l in lines if len("".join(s["text"] for s in l["spans"])) <= 2)
        if short / len(lines) > 0.6:
            dense.append(i)
    return dense


def build_report(args, doc, problem_pages, outdir):
    image_count = sum(len(p.get_images()) for p in doc)
    total_pages = len(doc)

    scan_notes = ""
    for p in problem_pages:
        if p["kind"] == "scan":
            scan_notes += f"> ⚠️ Page {p['page']}: looks like a pure-image page ({p['chars']} chars, {p['images']} images) — no text layer extracted. Check assets/ or OCR it separately.\n"
        else:
            scan_notes += f"> ℹ️ Page {p['page']}: blank page ({p['chars']} chars).\n"
    if problem_pages:
        scan_notes = "\n" + scan_notes + "\n"

    formula_notes = ""
    formula_pages = inspect_formula_pages(doc)
    if formula_pages:
        formula_notes = f"> ⚠️ Pages {_fmt_list(formula_pages)}: dense math — formulas extract poorly (one symbol per line). Verify manually if formulas matter.\n"

    cid_notes = ""
    cid_ratio = inspect_garbage(doc)
    if cid_ratio is not None:
        if cid_ratio > 0.01:
            cid_notes = f"> ⚠️ Font mapping missing ({cid_ratio:.1%} glyphs are `(cid:…)`) — some text may be garbled. Try a different source file.\n"

    return REPORT_TEMPLATE.format(
        input=args.input.name,
        pages=total_pages,
        image_count=image_count,
        scan_notes=scan_notes,
        formula_notes=formula_notes,
        cid_notes=cid_notes,
    )


def _fmt_list(pages):
    # compress consecutive pages: [1,2,3,5] -> "1-3, 5"
    out = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = p
    out.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", type=Path, help="input PDF")
    ap.add_argument("-o", "--outdir", type=Path, default=None, help="output directory (default: <input name>/ next to input)")
    ap.add_argument("-f", "--format", choices=["md", "html", "both"], default="md", help="output format (default: md)")
    ap.add_argument("--image-format", choices=["png", "jpg"], default="png", help="asset image format (default: png)")
    ap.add_argument("--scan-threshold", type=int, default=SCAN_CHAR_THRESHOLD, help="max chars per page to flag as scan/blank (default: 30)")
    ap.add_argument("--no-scan-check", action="store_true", help="skip scan page detection")
    args = ap.parse_args()

    if not args.input.exists():
        sys.exit(f"error: {args.input} not found")

    outdir = args.outdir or args.input.parent / args.input.stem
    outdir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(args.input)

    problem_pages = [] if args.no_scan_check else detect_problem_pages(doc, args.scan_threshold)
    report = build_report(args, doc, problem_pages, outdir)

    md = pymupdf4llm.to_markdown(
        str(args.input),
        write_images=True,
        image_path=str(outdir / "assets"),
        image_format=args.image_format,
    )
    # pymupdf4llm writes absolute image paths; relativize so the output folder is portable
    md = re.sub(r"!\[([^\]]*)\]\([^)]*?/assets/", r"![\1](assets/", md)

    if args.format in ("md", "both"):
        (outdir / f"{args.input.stem}.md").write_text(report + md, encoding="utf-8")

    if args.format in ("html", "both"):
        import markdown as md_render
        html = md_render.markdown(report + md, extensions=["tables", "fenced_code"])
        (outdir / f"{args.input.stem}.html").write_text(html, encoding="utf-8")

    scan_report = {"input": str(args.input), "threshold": args.scan_threshold,
                   "pages": len(doc), "problem_pages": problem_pages}
    (outdir / "scan_report.json").write_text(json.dumps(scan_report, ensure_ascii=False, indent=2), encoding="utf-8")

    for p in problem_pages:
        print(f"  {p['kind']} page {p['page']}: {p['chars']} chars, {p['images']} images")
    print(f"done: {outdir}")
    print(f"  {sum(1 for p in problem_pages if p['kind'] == 'scan')} scan-like page(s), "
          f"{sum(1 for p in problem_pages if p['kind'] == 'blank')} blank page(s)")


if __name__ == "__main__":
    main()
