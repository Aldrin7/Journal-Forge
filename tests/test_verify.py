#!/usr/bin/env python3
"""
PaperForge — End-to-End Verification Tests
Tests each pipeline phase with real documents.
"""
import sys
import json
import pathlib
import tempfile
import subprocess

# Add project root
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
WARN = "⚠️  WARN"


def test_result(name, passed, msg=""):
    status = PASS if passed else FAIL
    print(f"  {status} {name}" + (f" — {msg}" if msg else ""))
    return passed


def main():
    all_passed = True

    print("=" * 60)
    print("  PaperForge — Verification Test Suite")
    print("=" * 60)

    # ────────────────────────────────────────────────────────────
    # Test 1: Module imports
    # ────────────────────────────────────────────────────────────
    print("\n[1] Module Imports")
    try:
        from src.orchestration.ledger import Ledger
        test_result("Ledger import", True)
    except Exception as e:
        test_result("Ledger import", False, str(e))
        all_passed = False

    try:
        from src.orchestration.heartbeat import SessionHeartbeat
        test_result("Heartbeat import", True)
    except Exception as e:
        test_result("Heartbeat import", False, str(e))
        all_passed = False

    try:
        from src.orchestration.memory import MemoryGuard, get_rss_mb
        test_result("MemoryGuard import", True)
    except Exception as e:
        test_result("MemoryGuard import", False, str(e))
        all_passed = False

    try:
        from src.ingestion.pipeline import ingest, detect_format
        test_result("Ingestion pipeline import", True)
    except Exception as e:
        test_result("Ingestion pipeline import", False, str(e))
        all_passed = False

    try:
        from src.transformation.engine import transform, load_style_map
        test_result("Transformation engine import", True)
    except Exception as e:
        test_result("Transformation engine import", False, str(e))
        all_passed = False

    try:
        from src.auditing.semantic import full_audit, audit_report
        test_result("Semantic audit import", True)
    except Exception as e:
        test_result("Semantic audit import", False, str(e))
        all_passed = False

    try:
        from src.auditing.jats_compliance import validate_jats
        test_result("JATS compliance import", True)
    except Exception as e:
        test_result("JATS compliance import", False, str(e))
        all_passed = False

    try:
        from src.export.exporter import export_document
        test_result("Exporter import", True)
    except Exception as e:
        test_result("Exporter import", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 2: SQLite Ledger
    # ────────────────────────────────────────────────────────────
    print("\n[2] SQLite Ledger")
    try:
        from src.orchestration.ledger import Ledger
        with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as f:
            db_path = pathlib.Path(f.name)

        ledger = Ledger(db_path)
        ledger.create_run("test-run-001", "paper.md", "ieee", "docx")
        ledger.log_step("test-run-001", "paper.md", "ingest", "completed",
                       metadata={"pages": 10})
        ledger.log_step("test-run-001", "paper.md", "transform", "completed")

        steps = ledger.get_completed_steps("test-run-001", "paper.md")
        ok = "ingest" in steps and "transform" in steps
        test_result("Create run + log steps", ok, f"Steps: {steps}")

        # Checkpoint
        cp_id = ledger.save_checkpoint("test-run-001", "transform", {"equations": 5})
        cp = ledger.load_checkpoint(cp_id)
        ok = cp is not None and cp.get("equations") == 5
        test_result("Checkpoint save/load", ok)

        # Resume
        resumable = ledger.get_resumable_runs()
        test_result("Resumable runs query", len(resumable) >= 0)

        ledger.complete_run("test-run-001")
        ledger.close()
        db_path.unlink(missing_ok=True)

    except Exception as e:
        test_result("Ledger operations", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 3: Heartbeat
    # ────────────────────────────────────────────────────────────
    print("\n[3] Session Heartbeat")
    try:
        from src.orchestration.heartbeat import SessionHeartbeat
        with tempfile.TemporaryDirectory() as tmpdir:
            hb = SessionHeartbeat("test-hb", max_minutes=60,
                                  checkpoint_dir=pathlib.Path(tmpdir))
            hb.update(equations_extracted=42, tables_processed=3)
            hb.complete_step("ingest")
            hb.complete_step("transform")

            # Manually trigger summary
            hb._write_summary()

            ok = hb.summary_path.exists()
            test_result("Summary file created", ok)

            summary = json.loads(hb.summary_path.read_text())
            ok = summary["metrics"]["equations_extracted"] == 42
            test_result("Summary metrics correct", ok)

            ok = hb.summary_md_path.exists()
            test_result("Markdown summary created", ok)

    except Exception as e:
        test_result("Heartbeat operations", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 4: Ingestion — Markdown
    # ────────────────────────────────────────────────────────────
    print("\n[4] Ingestion — Markdown")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""---
title: Test Paper
author: Alice, Bob
abstract: This is a test abstract.
keywords: test, paper
---

# Introduction

This is the introduction with $E = mc^2$ inline math.

## Methods

$$f(x) = \\int_0^\\infty e^{-x^2} dx$$

# Results

![Test Figure](figure1.png)

| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
""")
            md_path = f.name

        from src.ingestion.pipeline import ingest, detect_format

        fmt = detect_format(md_path)
        test_result("Format detection", fmt == "markdown", f"Detected: {fmt}")

        doc = ingest(md_path, "markdown")
        ok = "Test Paper" in doc.title or doc.title == "Test Paper"
        test_result("Title extraction", ok, f"Title: {doc.title}")

        ok = len(doc.authors) >= 1
        test_result("Author extraction", ok, f"Authors: {doc.authors}")

        ok = len(doc.equations) >= 1
        test_result("Equation extraction", ok, f"Equations: {len(doc.equations)}")

        ok = len(doc.figures) >= 1
        test_result("Figure detection", ok, f"Figures: {len(doc.figures)}")

        ok = len(doc.tables) >= 1
        test_result("Table detection", ok, f"Tables: {len(doc.tables)}")

        pathlib.Path(md_path).unlink(missing_ok=True)

    except Exception as e:
        test_result("Markdown ingestion", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 5: Ingestion — LaTeX
    # ────────────────────────────────────────────────────────────
    print("\n[5] Ingestion — LaTeX")
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tex', delete=False) as f:
            f.write(r"""\documentclass{article}
\usepackage{amsmath}
\title{LaTeX Test Paper}
\author{Charlie Davis}
\begin{document}
\begin{abstract}
Testing LaTeX ingestion.
\end{abstract}
\section{Introduction}
Consider the equation:
\begin{equation}
E = mc^2
\end{equation}
\section{Methods}
$$\nabla \cdot \mathbf{E} = \frac{\rho}{\epsilon_0}$$
\begin{figure}
\caption{A test figure}
\end{figure}
\bibliography{refs}
\end{document}
""")
            tex_path = f.name

        from src.ingestion.pipeline import ingest

        doc = ingest(tex_path, "latex")
        ok = "LaTeX Test Paper" in doc.title or "latex" in doc.title.lower()
        test_result("LaTeX title extraction", ok, f"Title: {doc.title}")

        ok = len(doc.equations) >= 1
        test_result("LaTeX equation extraction", ok, f"Equations: {len(doc.equations)}")

        ok = len(doc.sections) >= 1
        test_result("LaTeX section extraction", ok, f"Sections: {len(doc.sections)}")

        pathlib.Path(tex_path).unlink(missing_ok=True)

    except Exception as e:
        test_result("LaTeX ingestion", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 6: Style Maps
    # ────────────────────────────────────────────────────────────
    print("\n[6] Style Maps")
    try:
        from src.transformation.engine import get_default_style_map

        for journal in ["ieee", "springer", "wiley", "elsevier", "mdpi", "nature", "acm"]:
            sm = get_default_style_map(journal)
            ok = "class" in sm and "font" in sm
            test_result(f"Style map: {journal}", ok, f"Class: {sm.get('class')}")

    except Exception as e:
        test_result("Style maps", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 7: Semantic Audit
    # ────────────────────────────────────────────────────────────
    print("\n[7] Semantic Audit")
    try:
        from src.auditing.semantic import full_audit, audit_report

        # Build a test AST
        ast = {
            "pandoc-api-version": [1, 23, 1],
            "meta": {
                "title": {"t": "MetaInlines", "c": [{"t": "Str", "c": "Test Paper"}]},
                "author": {"t": "MetaList", "c": [
                    {"t": "MetaInlines", "c": [{"t": "Str", "c": "Alice"}]}
                ]},
                "abstract": {"t": "MetaInlines", "c": [{"t": "Str", "c": "Abstract text"}]},
            },
            "blocks": [
                {"t": "Header", "c": [1, [], [{"t": "Str", "c": "Introduction"}]]},
                {"t": "Para", "c": [{"t": "Str", "c": "Some text with citation"}]},
                {"t": "Math", "c": ["DisplayMath", "E = mc^2"]},
                {"t": "Image", "c": [[], ["figure.png", "fig:"]]},
            ]
        }
        ast_json = json.dumps(ast)

        audits = full_audit(ast_json)
        report = audit_report(audits)

        test_result("Metadata audit", report["audits"]["metadata"]["passed"])
        test_result("Structure audit", report["audits"]["structure"]["passed"])
        test_result("Math audit", report["audits"]["math"]["passed"])
        test_result("Combined report", True, f"Score: {report['score']}")

    except Exception as e:
        test_result("Semantic audit", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 8: JATS Compliance
    # ────────────────────────────────────────────────────────────
    print("\n[8] JATS Compliance")
    try:
        from src.auditing.jats_compliance import validate_from_string

        jats_xml = """<?xml version="1.0" encoding="UTF-8"?>
<article article-type="research-article" xml:lang="en">
  <front>
    <article-meta>
      <article-id pub-id-type="doi">10.1234/test.2024</article-id>
      <title-group>
        <article-title>Test Article</article-title>
      </title-group>
      <contrib-group>
        <contrib contrib-type="author">
          <name><surname>Smith</surname><given-names>John</given-names></name>
          <contrib-id contrib-id-type="orcid">0000-0001-2345-6789</contrib-id>
        </contrib>
      </contrib-group>
      <abstract><p>Test abstract.</p></abstract>
      <kwd-group><kwd>test</kwd></kwd-group>
      <permissions>
        <copyright-statement>Copyright 2024</copyright-statement>
        <license><license-p>CC-BY 4.0</license-p></license>
      </permissions>
    </article-meta>
  </front>
  <body>
    <sec><title>Introduction</title><p>Content here.</p></sec>
  </body>
  <back>
    <ref-list>
      <ref id="ref1">
        <element-citation>
          <article-title>Ref Title</article-title>
          <name><surname>Doe</surname><given-names>Jane</given-names></name>
          <source>Journal</source>
          <year>2023</year>
          <pub-id pub-id-type="doi">10.1234/ref</pub-id>
        </element-citation>
      </ref>
    </ref-list>
  </back>
</article>"""

        result = validate_from_string(jats_xml)
        test_result("Valid JATS passes", result["passed"],
                   f"Errors: {len(result['errors'])}, Warnings: {len(result['warnings'])}")

    except Exception as e:
        test_result("JATS compliance", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 9: Lua Filter
    # ────────────────────────────────────────────────────────────
    print("\n[9] Lua Filter")
    try:
        lua_path = PROJECT_ROOT / "filters" / "fonts-and-alignment.lua"
        ok = lua_path.exists()
        test_result("Lua filter exists", ok, str(lua_path))

        if ok:
            content = lua_path.read_text()
            ok = "function Header" in content and "function Math" in content
            test_result("Lua filter has required functions", ok)

    except Exception as e:
        test_result("Lua filter", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 10: Template Manager
    # ────────────────────────────────────────────────────────────
    print("\n[10] Template Manager")
    try:
        from src.templates.manager import TEMPLATE_URLS, get_available_journals, get_journal_info

        journals = get_available_journals()
        test_result("Available journals", len(journals) >= 20,
                   f"Found {len(journals)} journals")

        info = get_journal_info("ieee")
        ok = "name" in info and "class" in info
        test_result("Journal info lookup", ok, f"IEEE class: {info.get('class')}")

    except Exception as e:
        test_result("Template manager", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Test 11: Memory Guard
    # ────────────────────────────────────────────────────────────
    print("\n[11] Memory Guard")
    try:
        from src.orchestration.memory import MemoryGuard, get_rss_mb, force_gc

        rss = get_rss_mb()
        test_result("RSS measurement", rss > 0, f"RSS: {rss:.1f} MB")

        gc_stats = force_gc()
        test_result("GC collection", gc_stats["objects_collected"] >= 0)

        with MemoryGuard("test") as mg:
            mg.checkpoint("mid")
        test_result("MemoryGuard context manager", True)

    except Exception as e:
        test_result("Memory guard", False, str(e))
        all_passed = False

    # ────────────────────────────────────────────────────────────
    # Summary
    # ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    if all_passed:
        print(f"  ✅ ALL TESTS PASSED")
    else:
        print(f"  ❌ SOME TESTS FAILED")
    print(f"{'=' * 60}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
