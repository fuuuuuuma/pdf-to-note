#!/usr/bin/env python3
"""Compare article-body HTML with saved note-body HTML; never publishes."""

import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


def normalize(value):
    return re.sub(r"\s+", "", value)


class ArticleParser(HTMLParser):
    """Ignore captions/UI, retain visible prose and the exact heading sequence."""

    EXCLUDED = {"figcaption", "script", "style", "button", "svg"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text = []
        self.headings = []
        self.active_heading = None
        self.images = []

    def ignored(self):
        return any(tag in self.EXCLUDED for tag in self.stack)

    def handle_starttag(self, tag, attrs):
        if tag == "img" and not self.ignored():
            src = dict(attrs).get("src", "")
            self.images.append(src)
        if tag not in self.VOID:
            self.stack.append(tag)
        if re.fullmatch(r"h[1-6]", tag) and not self.ignored():
            self.active_heading = {"level": int(tag[1]), "parts": []}

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.active_heading and tag == f"h{self.active_heading['level']}":
            self.headings.append({"level": self.active_heading["level"],
                                  "text": normalize("".join(self.active_heading["parts"]))})
            self.active_heading = None
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if not self.ignored():
            self.text.append(data)
            if self.active_heading:
                self.active_heading["parts"].append(data)

    def body_text(self):
        return normalize("".join(self.text))


def read_body(path):
    parser = ArticleParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def first_difference(left, right):
    for index, (a, b) in enumerate(zip(left, right)):
        if a != b:
            return index
    return min(len(left), len(right)) if left != right else None


def main():
    args_parser = argparse.ArgumentParser(description=__doc__)
    args_parser.add_argument("--source", type=Path, required=True)
    args_parser.add_argument("--saved", type=Path, required=True)
    args_parser.add_argument("--expected-images", type=int)
    args_parser.add_argument("--require-remote", action="store_true")
    args_parser.add_argument("--report", type=Path, required=True, help="New JSON report path")
    args = args_parser.parse_args()
    try:
        if args.report.exists():
            raise ValueError("Report already exists; choose a new path")
        if args.expected_images is not None and args.expected_images < 0:
            raise ValueError("Expected image count cannot be negative")
        source, saved = read_body(args.source), read_body(args.saved)
        original, actual = source.body_text(), saved.body_text()
        if not original:
            raise ValueError("Source body is empty")
        schemes = [urlsplit(src).scheme for src in saved.images]
        https_images = sum(scheme == "https" for scheme in schemes)
        checks = {
            "body_preserved": original == actual,
            "headings_preserved": source.headings == saved.headings,
            "image_count_matches": args.expected_images is None or len(saved.images) == args.expected_images,
            "remote_images_present": not args.require_remote or https_images == len(saved.images),
        }
        report = {
            "ok": all(checks.values()), "checks": checks,
            "source_characters_without_whitespace": len(original),
            "saved_characters_without_whitespace": len(actual),
            "source_text_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "saved_text_sha256": hashlib.sha256(actual.encode()).hexdigest(),
            "first_difference_index": first_difference(original, actual),
            "source_headings": source.headings, "saved_headings": saved.headings,
            "inline_images": len(saved.images), "expected_images": args.expected_images,
            "https_images": https_images,
            "not_verified": ["PDF topic coverage", "caption correctness", "image loading",
                             "image placement", "cover image", "publication"],
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps({"ok": report["ok"], "checks": checks,
                          "inline_images": len(saved.images), "report": str(args.report)},
                         ensure_ascii=False))
        if not report["ok"]:
            args_parser.exit(1)
    except (OSError, ValueError) as error:
        args_parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
