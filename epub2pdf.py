#!/usr/bin/env python3
"""Simple EPUB -> PDF converter. Renders the book with headless Edge/Chrome.

Usage: python epub2pdf.py book.epub [out.pdf] [options]
Run with -h for tweaks (page size, margins, font, keep book CSS, ...).
"""
import argparse
import posixpath
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

CLEAN_CSS = """
@page {{ size: {page}; margin: {margin}; }}
html {{ font-size: {font_size}pt; }}
body {{ font-family: {font}; line-height: {line_height}; text-align: {align}; margin: 0; }}
section.chapter {{ break-before: page; }}
section.chapter:first-child {{ break-before: auto; }}
img, svg {{ max-width: 100%; max-height: 95vh; height: auto; }}
h1, h2, h3, h4 {{ break-after: avoid; }}
img, table, figure, pre {{ break-inside: avoid; }}
table {{ border-collapse: collapse; max-width: 100%; }}
td, th {{ border: 1px solid #999; padding: 2px 6px; }}
"""


def read_book(zf):
    """Return (title, [spine paths in zip], opf_dir)."""
    container = BeautifulSoup(zf.read("META-INF/container.xml"), "xml")
    opf_path = container.find("rootfile")["full-path"]
    opf_dir = posixpath.dirname(opf_path)
    opf = BeautifulSoup(zf.read(opf_path), "xml")
    manifest = {i["id"]: i for i in opf.find("manifest").find_all("item")}
    spine = []
    for ref in opf.find("spine").find_all("itemref"):
        item = manifest.get(ref["idref"])
        if item is None or ref.get("linear") == "no":
            continue
        if "html" not in item.get("media-type", ""):
            continue
        spine.append(posixpath.normpath(posixpath.join(opf_dir, unquote(item["href"]))))
    title = opf.find("dc:title") or opf.find("title")
    return (title.get_text(strip=True) if title else "Book"), spine


def rewrite_urls(soup, chapter_path, chapter_id):
    """Make resource URLs relative to the extraction root; fix internal links."""
    base = posixpath.dirname(chapter_path)

    def fix(url):
        p = urlparse(url)
        if p.scheme or url.startswith("data:"):
            return url
        return posixpath.normpath(posixpath.join(base, unquote(p.path)))

    for tag in soup.find_all(src=True):
        tag["src"] = fix(tag["src"])
    for tag in soup.find_all(["image", "use"]):  # svg
        for attr in ("href", "xlink:href"):
            if tag.get(attr) and not tag[attr].startswith("#"):
                tag[attr] = fix(tag[attr])
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#"):
            a["href"] = "#" + chapter_id + "-" + href[1:]
        elif not urlparse(href).scheme:
            del a["href"]  # link to another chapter file: not resolvable, drop
    for tag in soup.find_all(id=True):
        tag["id"] = chapter_id + "-" + tag["id"]


def build_html(zf, spine, root, args):
    chapters, styles = [], []
    for n, path in enumerate(spine):
        soup = BeautifulSoup(zf.read(path), "lxml")
        body = soup.body
        if body is None:
            continue
        if args.keep_css:
            for link in soup.find_all("link", rel=lambda r: r and "stylesheet" in r):
                styles.append(f'<link rel="stylesheet" href="{fix_css_href(path, link["href"])}">')
            for st in soup.find_all("style"):
                styles.append(str(st))
        for tag in body.find_all(["script"]):
            tag.decompose()
        if not args.keep_css:
            for tag in body.find_all(style=True):
                del tag["style"]
            for tag in body.find_all(["font", "center"]):
                tag.unwrap()
        if args.no_images:
            for tag in body.find_all(["img", "svg"]):
                tag.decompose()
        rewrite_urls(body, path, f"c{n}")
        chapters.append(f'<section class="chapter">{body.decode_contents()}</section>')
    css = CLEAN_CSS.format(
        page=args.page, margin=args.margin, font_size=args.font_size, font=args.font,
        line_height=args.line_height, align=args.align,
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        + "".join(dict.fromkeys(styles))  # dedupe, keep order
        + f"<style>{css}{args.extra_css}</style></head><body>"
        + "\n".join(chapters)
        + "</body></html>"
    )


def fix_css_href(chapter_path, href):
    return posixpath.normpath(posixpath.join(posixpath.dirname(chapter_path), unquote(href)))


def make_parser():
    ap = argparse.ArgumentParser(description="Convert EPUB to PDF.")
    ap.add_argument("epub")
    ap.add_argument("pdf", nargs="?", help="output path (default: next to the epub)")
    ap.add_argument("--page", default="A5", help="page size: A4, A5, Letter, or e.g. '6in 9in' (default A5)")
    ap.add_argument("--margin", default="15mm", help="page margin (default 15mm)")
    ap.add_argument("--font-size", default="11", help="base font size in pt (default 11)")
    ap.add_argument("--font", default="Georgia, 'Times New Roman', serif", help="CSS font-family")
    ap.add_argument("--line-height", default="1.4")
    ap.add_argument("--align", default="left", choices=["left", "justify"])
    ap.add_argument("--keep-css", action="store_true", help="use the book's own CSS (default: clean style)")
    ap.add_argument("--no-images", action="store_true", help="drop all images")
    ap.add_argument("--extra-css", default="", help="extra CSS appended last, for one-off fixes")
    ap.add_argument("--html", action="store_true", help="also keep the intermediate HTML next to the PDF for debugging")
    ap.add_argument("--browser", default="msedge", help="playwright channel: msedge, chrome, or 'chromium'")
    return ap


def convert(args):
    """Convert args.epub to args.pdf (or next to the epub). Returns (title, sections, out)."""
    epub = Path(args.epub)
    out = Path(args.pdf) if args.pdf else epub.with_suffix(".pdf")
    root = Path(tempfile.mkdtemp(prefix="epub2pdf_"))
    try:
        with zipfile.ZipFile(epub) as zf:
            zf.extractall(root)
            title, spine = read_book(zf)
            html = build_html(zf, spine, root, args)
        page_file = root / "_book.html"
        page_file.write_text(html, encoding="utf-8")
        if args.html:
            shutil.copy(page_file, out.with_suffix(".html"))
        with sync_playwright() as p:
            kw = {} if args.browser == "chromium" else {"channel": args.browser}
            browser = p.chromium.launch(**kw)
            page = browser.new_page()
            page.goto(page_file.as_uri())
            page.wait_for_load_state("networkidle")
            page.pdf(path=str(out), prefer_css_page_size=True, print_background=True)
            browser.close()
        return title, len(spine), out
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    title, n, out = convert(make_parser().parse_args())
    print(f"{title}: {n} sections -> {out}")


if __name__ == "__main__":
    main()
