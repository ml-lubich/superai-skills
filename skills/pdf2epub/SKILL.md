---
name: pdf2epub
description: Convert any PDF into clean, reflowable, valid EPUB with high-res images and zero XML parsing errors.
---

# pdf2epub Skill

Converts PDFs into clean, reflowable, strictly-validated EPUB ebooks.

## CLI Location
- `pdf2epub` is installed at `~/.local/bin/pdf2epub` and `~/bin/pdf2epub`

## Key Capabilities
- Extracts structured paragraph text and preserves chapter headings.
- Extracts figures and high-resolution images (`OEBPS/images/img_*.jpeg|png`) into responsive markup (`max-width: 100%`).
- Sanitizes XML control characters (`\x00-\x08`, `\x0B-\x0C`, `\x0E-\x1F`) and properly escapes entities (`&`, `<`, `>`, `"`) to prevent e-reader XML crashes (Apple Books, Calibre, Kindle).
- Complies strictly with EPUB 2.0 container, OPF manifest/spine, and NCX specifications.

## Usage
```bash
# Convert in-place (creates document.epub):
pdf2epub document.pdf

# Custom output destination:
pdf2epub document.pdf -o ~/Books/document.epub

# Custom metadata:
pdf2epub document.pdf -t "My Book Title" -a "Author Name"

# Disable image extraction:
pdf2epub document.pdf --no-images
```
