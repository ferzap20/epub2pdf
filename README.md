# epub2pdf

Simple EPUB to PDF converter. Renders the book with headless Edge/Chrome using a clean stylesheet, so the output avoids the clutter other converters produce.

## Setup

```
pip install playwright beautifulsoup4 lxml
```

Requires Python 3 and Microsoft Edge (or Chrome, with `--browser chrome`).

## Usage

GUI: double-click `EPUB to PDF.bat`.

Command line:

```
python epub2pdf.py book.epub [out.pdf] [--page A4] [--margin 15mm] [--font-size 11] [--align justify] [--keep-css] [--no-images] [--extra-css "..."]
```

Defaults: A5, 15mm margin, 11pt Georgia, left-aligned, clean styling, images kept.

Limitations: links between chapters are dropped and no PDF bookmarks are generated.
