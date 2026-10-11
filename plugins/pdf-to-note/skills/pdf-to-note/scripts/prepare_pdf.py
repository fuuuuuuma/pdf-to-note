#!/usr/bin/env python3
"""Extract every PDF page and render selected slides using Poppler; no uploads."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run(command):
    return subprocess.run(command, check=True, capture_output=True, text=True)


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def parse_pages(value):
    pages = set()
    if not value:
        return pages
    for item in value.split(","):
        bounds = item.strip().split("-")
        if len(bounds) == 1:
            pages.add(int(bounds[0]))
        elif len(bounds) == 2:
            start, end = map(int, bounds)
            if start > end:
                raise ValueError("Page ranges must be ascending")
            pages.update(range(start, end + 1))
        else:
            raise ValueError("Use comma-separated pages or ranges, e.g. 2,5-7")
    return pages


def parse_crop(value):
    parts = [int(part) for part in value.split(":")]
    if len(parts) != 5:
        raise ValueError("Crop must be page:x:y:width:height")
    page, x, y, width, height = parts
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("Crop coordinates must be nonnegative; dimensions positive")
    return page, x, y, width, height


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New output directory")
    parser.add_argument("--pages", default="", help="1-based pages, e.g. 3,8-10")
    parser.add_argument("--crop", action="append", default=[], help="page:x:y:width:height")
    parser.add_argument("--scale-to", type=int, default=1600, help="Longest rendered side")
    args = parser.parse_args()

    try:
        pdf = args.pdf.expanduser().resolve(strict=True)
        output = args.output.expanduser().resolve()
        if not pdf.is_file():
            raise ValueError("PDF input must be a file")
        if output.exists():
            raise ValueError("Output already exists; choose a new directory")
        if args.scale_to <= 0:
            raise ValueError("Scale must be positive")
        pages = parse_pages(args.pages)
        crops = [parse_crop(item) for item in args.crop]
        if len(crops) != len(set(crops)):
            raise ValueError("Duplicate crop specification")
        required = ["pdfinfo", "pdftotext"] + (["pdftoppm"] if pages or crops else [])
        missing = [tool for tool in required if not shutil.which(tool)]
        if missing:
            raise ValueError("Missing Poppler tools: " + ", ".join(missing))
        info = run(["pdfinfo", str(pdf)]).stdout
        match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
        if not match:
            raise ValueError("Unable to determine PDF page count")
        count = int(match.group(1))
        selected = pages | {crop[0] for crop in crops}
        if any(page < 1 or page > count for page in selected):
            raise ValueError(f"Selected pages must be in 1..{count}")
        raw = run(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"]).stdout
        sections = raw.split("\f")
        if len(sections) == count + 1 and not sections[-1].strip():
            sections.pop()
        if len(sections) != count:
            raise ValueError(f"Text page count mismatch: {len(sections)} vs {count}")

        output.mkdir(parents=True, exist_ok=False)
        page_index = []
        text_blocks = []
        for number, section in enumerate(sections, 1):
            content = section.strip()
            text_blocks.append(f"# PDF page {number}\n\n{content}\n")
            page_index.append({
                "page": number,
                "text_characters": len(content),
                "needs_visual_check": not bool(content),
            })
        (output / "pdf-full.txt").write_text("\n".join(text_blocks), encoding="utf-8")

        rendered = []
        jobs = [(page, None) for page in sorted(pages)]
        jobs.extend((crop[0], crop[1:]) for crop in crops)
        for page, crop in jobs:
            suffix = "" if crop is None else "-crop-" + "-".join(map(str, crop))
            stem = output / f"page-{page}{suffix}"
            command = ["pdftoppm", "-f", str(page), "-l", str(page),
                       "-scale-to", str(args.scale_to), "-png", "-singlefile"]
            if crop:
                x, y, width, height = crop
                command += ["-x", str(x), "-y", str(y), "-W", str(width), "-H", str(height)]
            command += [str(pdf), str(stem)]
            run(command)
            image_path = stem.with_suffix(".png")
            if not image_path.is_file() or image_path.stat().st_size == 0:
                raise ValueError(f"Rendered image missing for page {page}")
            rendered.append({"source_page": page, "image_path": str(image_path),
                             "sha256": digest(image_path), "crop": crop,
                             "scale_to": args.scale_to})

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_pdf": str(pdf), "source_sha256": digest(pdf), "source_pages": count,
            "extracted_pages": len(sections), "pages": page_index, "images": rendered,
            "visual_review_complete": False,
            "note": "Text extraction is not proof of reading or visual completeness.",
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"output": str(output), "pages": count,
                          "rendered_images": len(rendered),
                          "empty_text_pages": sum(p["needs_visual_check"] for p in page_index)},
                         ensure_ascii=False))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            parser.exit(1, "Poppler failed: " + error.stderr[:500] + "\n")
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
