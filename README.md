# KDPEasy Maze Creator

Part of the KDPEasy Suite — free/paid tools for KDP creators.

Generate a print-ready Maze activity book in seconds, complete with an answer key section.

## Features (v1)
- Any KDP trim size preset: Letter, Square (8.5x8.5), 8x10, 6x9, A4, A5 — portrait or landscape
- **Maze**: choose number of mazes, size (Small 10x10, Medium 15x15, Large 20x20), generated via randomized DFS (a perfect maze — exactly one path between entrance and exit)
- Optional answer key section at the end (solution path traced in gray, so it's clearly visible against the black maze walls without being mistaken for a wall)
- "Start numbering at" — combine mazes from different batches into one book without renumbering by hand
- Cover page with optional photo, plus a free AI cover-art prompt generator (same pattern as the Word Search Activity Creator)
- On-screen preview before downloading, rendered from the actual PDF via PyMuPDF
- Optional PNG export: each page as a separate 300 DPI PNG, packaged into one ZIP

## Stack
Streamlit + fpdf2 (pinned to 2.8.8) + PyMuPDF + Pillow (pure Python, no system dependencies, no paid API — runs free on Streamlit Cloud). Maze generation/solving is pure algorithmic Python, no AI involved.

Password-protected, same pattern as the rest of the KDPEasy Suite. Passwords are checked against `PASSWORD_EXPIRY` in `app.py` — a value of `None` means permanent access, a date means the password stops working after that day (used for time-limited trials).
