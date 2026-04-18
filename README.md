# PaperForge — Universal Agentic Research-to-Journal Converter

**PaperForge** is a self-contained, offline-first system that converts academic research papers from draft formats (DOCX, MD, LaTeX, JATS XML) into camera-ready journal submissions for IEEE, Springer Nature, Wiley, Elsevier, MDPI, Nature, ACM, PLOS, Frontiers, BMJ, ACS, Taylor & Francis, Oxford, and 50+ more journal families.

## Features

- **Two Workflow Modes:**
  1. **Upload Mode** — Load existing manuscript (.docx, .md, .tex, .jats)
  2. **Universal Template Mode** — Build paper section-by-section from a universal IEEE-style template, then convert to any target journal

- **Full Format Support:**
  - Input: DOCX, Markdown, LaTeX, JATS XML
  - Output: PDF, DOCX, LaTeX, JATS XML, PMC XML, HTML, ePub

- **Mathematical Fidelity:**
  - Pure-Python OMML→LaTeX converter (no external deps)
  - Fractions, superscripts, subscripts, radicals, integrals, matrices, accents
  - OMML ↔ LaTeX lossless round-tripping

- **44+ Journal Templates:**
  - IEEE (all transactions), Springer Nature, Wiley, Elsevier, MDPI, Nature, ACM, PLOS, Frontiers, BMJ, ACS, Taylor & Francis, Oxford
  - Each template includes style maps, Lua filters, and verification tests

- **Robust Auditing:**
  - Semantic audit (citations, metadata, structure, math, figures)
  - Visual SSIM regression (pixel-level PDF comparison)
  - JATS PMC compliance (22-rule validation)
  - Automatic "Verify and Correct" loops

- **Dual Deployment:**
  1. **Desktop App** (PyInstaller + Electron) — Standalone executable
  2. **Web App** (FastAPI + React) — Browser-based interface

## Architecture

```
+--------------------------------------------------------------+
| MiMo-Claw Orchestrator (MiMo-V2-Pro)                         |
| • Session manager — enforces 45-min wall-time                |
| • MemoryGuard — sub-process isolation & gc.collect()         |
+---------------------------+----------------------------------+
                            |
                            | (SQLite ledger + JSON checkpoints)
+---------------------------v----------------------------------+
| Persistence Layer                                             |
| • ledger.sqlite — file_id, step, last_row, timestamps        |
| • checkpoints/ — agent_state.json, AST*.json, logs           |
+---------------------------+----------------------------------+
                            |
         +----------------+------------------+-------------------+
         |                |                  |                   |
+--------v-----+  +------v------+  +-------v------+  +--------v--------+
| Ingestion    |  | Transform   |  | Auditing     |  | Packaging       |
| (docx, md,   |  | (Pandoc AST |  | (semantic +  |  | (PyInstaller    |
|  tex, jats)  |  | + Lua filt.)|  | visual diff) |  |  / Electron)    |
+--------------+  +-------------+  +--------------+  +-----------------+
```

## Technical Stack

| Layer | Technology |
|-------|-----------|
| Core | Python 3.12 |
| Document conversion | Pandoc ≥ 3.3 (subprocess) |
| LaTeX engine | Tectonic (on-demand packages) |
| Math handling | Pure-Python OMML→LaTeX + Pandoc AST |
| Visual regression | pdf-visual-diff (Node.js) or Python SSIM |
| Citations | CSL engine (14 bundled styles) |
| State | SQLite WAL-mode |
| Packaging | PyInstaller (directory mode) |
| Desktop UI | Electron + React |
| Web UI | FastAPI + React + Vite |

All binaries bundled — works on a completely isolated machine.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Convert a paper
python3 pipeline/translator.py paper.md --journal ieee --format docx
python3 pipeline/translator.py thesis.tex --journal springer
python3 pipeline/translator.py draft.docx --journal acm --format pdf

# List available journals
python3 pipeline/translator.py --list-journals

# Desktop app
cd electron && npm start

# Web app
cd web/backend && uvicorn app.main:app --reload
cd web/frontend && npm run dev
```

## Constraints

- ≤ 3 GB RAM ceiling
- 45–50 min ephemeral sessions
- Fully offline (all binaries bundled)
- SQLite WAL-mode checkpointing for session resumption

## Project Structure

```
PaperForge/
├── src/
│   ├── ingestion/       # DOCX, LaTeX, MD, JATS parsers + OMML converter
│   ├── transformation/  # AST normalization, Lua filters, style maps
│   ├── auditing/        # Semantic, visual SSIM, JATS compliance
│   ├── orchestration/   # Ledger, heartbeat, memory guard
│   ├── export/          # PDF, DOCX, LaTeX, JATS renderers + Tectonic
│   └── templates/       # Journal template manager
├── filters/             # Pandoc Lua filters (IEEE, Springer, Nature, etc.)
├── data/csl-styles/     # 14 CSL citation style files
├── scripts/             # Visual diff (Node.js)
├── web/                 # FastAPI backend + React frontend
├── electron/            # Desktop app wrapper
├── pipeline/            # Main orchestrator (CLI)
├── tests/               # Verification, OMML, and E2E tests
├── build/               # PyInstaller spec
└── requirements.txt     # Python dependencies
```

## Testing

```bash
# Core verification (11 tests)
python3 tests/test_verify.py

# OMML → LaTeX conversion (10 tests)
python3 tests/test_omml.py

# End-to-end pipeline (20+ tests)
python3 tests/test_e2e.py
```

## License

MIT
