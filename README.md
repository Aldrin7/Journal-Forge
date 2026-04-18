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
  - Equations, formulas, tables, figures, symbols all convert correctly
  - OMML ↔ LaTeX lossless round-tripping
  - Complex multi-line derivations preserved

- **40+ Journal Templates:**
  - IEEE (all transactions), Springer Nature, Wiley, Elsevier, MDPI, Nature, ACM, PLOS, Frontiers, BMJ, ACS, Taylor & Francis, Oxford
  - Each template includes style maps, Lua filters, and verification tests

- **Robust Auditing:**
  - Semantic audit (citations, metadata, structure)
  - Visual SSIM regression (pixel-level PDF comparison)
  - JATS PMC compliance (22-rule validation)
  - Automatic "Verify and Correct" loops

- **Dual Deployment:**
  1. **Desktop App** (PyInstaller + Electron) — Standalone executable
  2. **Web App** (FastAPI + React) — Browser-based interface

## Architecture

```
┌─────────────────────────────────────────────────────┐
│           PaperForge Orchestrator                    │
│  Session Manager · MemoryGuard · Checkpoint Resume   │
├──────────┬──────────┬──────────┬────────────────────┤
│  SQLite  │Ingestion │ Transform│ Auditing + Export   │
│  Ledger  │Pipeline  │ Engine   │ Semantic/Visual/JATS│
└──────────┴──────────┴──────────┴────────────────────┘
```

## Quick Start

```bash
# Convert a paper
python3 pipeline/translator.py paper.md --journal ieee --format docx
python3 pipeline/translator.py thesis.tex --journal springer
python3 pipeline/translator.py draft.docx --journal acm

# Universal template mode
python3 pipeline/translator.py --template --journal wiley --format pdf

# Desktop app
cd electron && npm start

# Web app
cd web/backend && uvicorn app.main:app --reload
cd web/frontend && npm run dev
```

## Constraints

- 3 GB RAM ceiling
- 45-minute ephemeral sessions
- Fully offline (all binaries bundled)
- SQLite WAL-mode checkpointing for session resumption

## Project Structure

```
PaperForge/
├── src/
│   ├── ingestion/       # DOCX, LaTeX, MD, JATS parsers
│   ├── transformation/  # AST normalization, Lua filters, style maps
│   ├── auditing/        # Semantic, visual, JATS compliance
│   ├── orchestration/   # Ledger, heartbeat, memory guard
│   ├── export/          # PDF, DOCX, LaTeX, JATS renderers
│   └── ui/              # Shared UI components
├── filters/             # Pandoc Lua filters
├── scripts/             # Visual diff, template download
├── templates/           # 40+ journal style maps
├── web/                 # FastAPI backend + React frontend
├── electron/            # Desktop app wrapper
├── pipeline/            # Main orchestrator
├── tests/               # Verification tests
└── data/                # CSL styles, template cache
```

## License

MIT
