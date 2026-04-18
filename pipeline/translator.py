#!/usr/bin/env python3
"""
PaperForge — Main Pipeline Orchestrator
Converts academic papers to camera-ready journal submissions.
Supports both upload mode and universal template mode.
"""
import argparse
import json
import pathlib
import sys
import uuid
import datetime
import gc
import tempfile
import shutil
from typing import Optional, List, Dict, Any

# Add project root to path
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.ledger import Ledger
from src.orchestration.heartbeat import SessionHeartbeat
from src.orchestration.memory import MemoryGuard, get_rss_mb, force_gc
from src.ingestion.pipeline import ingest, UnifiedDocument, detect_format
from src.transformation.engine import transform, TransformResult, get_default_style_map
from src.auditing.semantic import full_audit, audit_report
from src.auditing.jats_compliance import validate_jats
from src.export.exporter import export_document, export_all_formats, ExportResult


PIPELINE_STEPS = [
    "ingest",
    "transform",
    "audit",
    "render",
    "finalize"
]


def generate_run_id() -> str:
    """Generate a unique run ID."""
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"{ts}-{short_uuid}"


def run_pipeline(
    input_file: str,
    journal: str = "ieee",
    output_format: str = "docx",
    output_dir: Optional[str] = None,
    resume_run_id: Optional[str] = None,
    max_minutes: int = 45,
    skip_visual_audit: bool = False,
    bibliography: Optional[str] = None,
    quiet: bool = False,
) -> Dict[str, Any]:
    """
    Run the full PaperForge pipeline.
    
    Args:
        input_file: Path to input document
        journal: Target journal identifier
        output_format: Output format (pdf, docx, latex, html, jats)
        output_dir: Output directory (default: output/<run_id>)
        resume_run_id: Resume a previous run
        max_minutes: Session wall-time limit
        skip_visual_audit: Skip visual SSIM audit
        bibliography: Path to .bib file
        quiet: Suppress progress output
    
    Returns:
        Dict with run results
    """
    # Initialize
    run_id = resume_run_id or generate_run_id()
    ledger = Ledger()
    file_id = pathlib.Path(input_file).name

    if not quiet:
        print(f"\n{'='*60}")
        print(f"  PaperForge — Agentic Research-to-Journal Converter")
        print(f"{'='*60}")
        print(f"  Run ID:    {run_id}")
        print(f"  Input:     {input_file}")
        print(f"  Journal:   {journal}")
        print(f"  Output:    {output_format}")
        print(f"  Memory:    {get_rss_mb():.0f} MB")
        print(f"{'='*60}\n")

    # Create run
    ledger.create_run(run_id, file_id, journal, output_format)

    # Set up output directory
    if output_dir:
        out_dir = pathlib.Path(output_dir)
    else:
        out_dir = PROJECT_ROOT / "output" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Set up heartbeat
    heartbeat = SessionHeartbeat(run_id, max_minutes, out_dir)
    heartbeat.journal = journal
    heartbeat.input_file = input_file
    heartbeat.output_format = output_format
    heartbeat.start()

    result = {
        "run_id": run_id,
        "file_id": file_id,
        "journal": journal,
        "input_file": input_file,
        "output_format": output_format,
        "output_dir": str(out_dir),
        "steps": {},
        "outputs": {},
        "audit": {},
        "success": False,
        "errors": [],
        "warnings": [],
    }

    completed_steps = ledger.get_completed_steps(run_id, file_id) if resume_run_id else []

    try:
        # ═══════════════════════════════════════════════════════════════
        # PHASE 1: INGESTION
        # ═══════════════════════════════════════════════════════════════
        if "ingest" not in completed_steps:
            if not quiet:
                print("[1/5] 📥 Ingesting document...")
            heartbeat.current_step = "ingest"

            with MemoryGuard("ingestion") as mg:
                doc = ingest(input_file)
                mg.checkpoint("document_parsed")

                # Save ingested state
                ingest_state = {
                    "title": doc.title,
                    "authors": doc.authors,
                    "abstract": doc.abstract,
                    "keywords": doc.keywords,
                    "source_format": doc.source_format,
                    "num_equations": len(doc.equations),
                    "num_figures": len(doc.figures),
                    "num_tables": len(doc.tables),
                    "num_references": len(doc.references),
                }

                # Save AST if available
                if doc.pandoc_json:
                    ast_path = out_dir / "ast_ingested.json"
                    ast_path.write_text(doc.pandoc_json)
                    ingest_state["ast_path"] = str(ast_path)

                # Save checkpoint
                ledger.save_checkpoint(run_id, "ingest", ingest_state)
                ledger.log_step(run_id, file_id, "ingest", "completed",
                               metadata=ingest_state)

            heartbeat.update(
                equations_extracted=len(doc.equations),
                figures_processed=len(doc.figures),
                tables_processed=len(doc.tables),
            )
            heartbeat.complete_step("ingest")

            if not quiet:
                print(f"  ✅ Ingested: {doc.title[:60]}...")
                print(f"     Equations: {len(doc.equations)}, Figures: {len(doc.figures)}, "
                      f"Tables: {len(doc.tables)}")
        else:
            if not quiet:
                print("[1/5] ⏭️  Ingestion already completed (resuming)")
            doc = ingest(input_file)

        result["steps"]["ingest"] = "completed"

        # ═══════════════════════════════════════════════════════════════
        # PHASE 2: TRANSFORMATION
        # ═══════════════════════════════════════════════════════════════
        if "transform" not in completed_steps:
            if not quiet:
                print("[2/5] 🔄 Transforming document...")
            heartbeat.current_step = "transform"

            with MemoryGuard("transformation") as mg:
                # Get AST
                ast_json = doc.pandoc_json
                if not ast_json:
                    # Build minimal AST from parsed document
                    ast_json = _build_ast_from_doc(doc)
                    if not quiet:
                        print("  ⚠️  Built minimal AST (Pandoc unavailable)")

                mg.checkpoint("ast_ready")

                # Transform
                transform_result = transform(ast_json, journal)
                mg.checkpoint("transform_complete")

                # Save transformed AST
                ast_out_path = out_dir / "ast_transformed.json"
                ast_out_path.write_text(transform_result.ast_json)

                # Save style map
                style_path = out_dir / "style_map.json"
                with open(style_path, 'w') as f:
                    json.dump(transform_result.style_map, f, indent=2)

                # Save checkpoint
                transform_state = {
                    "num_equations": len(transform_result.normalized_equations),
                    "applied_filters": transform_result.applied_filters,
                    "warnings": transform_result.warnings,
                    "style_map_path": str(style_path),
                }
                ledger.save_checkpoint(run_id, "transform", transform_state)
                ledger.log_step(run_id, file_id, "transform", "completed",
                               metadata=transform_state)

            heartbeat.complete_step("transform")

            if not quiet:
                print(f"  ✅ Transformed: {len(transform_result.normalized_equations)} equations normalized")
                for f in transform_result.applied_filters:
                    print(f"     Filter: {f}")
        else:
            if not quiet:
                print("[2/5] ⏭️  Transformation already completed (resuming)")

        result["steps"]["transform"] = "completed"

        # ═══════════════════════════════════════════════════════════════
        # PHASE 3: AUDITING
        # ═══════════════════════════════════════════════════════════════
        if "audit" not in completed_steps:
            if not quiet:
                print("[3/5] 🔍 Running audits...")
            heartbeat.current_step = "audit"

            with MemoryGuard("auditing") as mg:
                ast_path = out_dir / "ast_transformed.json"
                ast_json = ast_path.read_text() if ast_path.exists() else doc.pandoc_json

                # Semantic audit
                audits = full_audit(ast_json)
                report = audit_report(audits)
                mg.checkpoint("semantic_audit")

                # Save audit report
                audit_path = out_dir / "audit_report.json"
                with open(audit_path, 'w') as f:
                    json.dump(report, f, indent=2, default=str)

                # JATS compliance (if outputting JATS)
                jats_result = None
                if output_format == "jats":
                    jats_path = out_dir / "output.jats"
                    if jats_path.exists():
                        jats_result = validate_jats(str(jats_path))
                        mg.checkpoint("jats_audit")

                ledger.save_checkpoint(run_id, "audit", report)
                ledger.log_step(run_id, file_id, "audit", "completed",
                               metadata={"score": report["score"]})

            result["audit"] = report
            heartbeat.complete_step("audit")

            if not quiet:
                status = "✅ PASSED" if report["passed"] else "❌ FAILED"
                print(f"  {status} — Score: {report['score']:.0f}/100")
                print(f"     Errors: {report['total_errors']}, Warnings: {report['total_warnings']}")

                if report["total_errors"] > 0:
                    for audit_name, audit_data in report["audits"].items():
                        for err in audit_data["errors"]:
                            print(f"     ❌ [{audit_name}] {err['msg']}")

                if report["total_warnings"] > 0 and not quiet:
                    for audit_name, audit_data in report["audits"].items():
                        for warn in audit_data["warnings"][:3]:  # Limit warnings shown
                            print(f"     ⚠️  [{audit_name}] {warn['msg']}")
        else:
            if not quiet:
                print("[3/5] ⏭️  Audit already completed (resuming)")

        result["steps"]["audit"] = "completed"

        # ═══════════════════════════════════════════════════════════════
        # PHASE 4: RENDERING
        # ═══════════════════════════════════════════════════════════════
        if "render" not in completed_steps:
            if not quiet:
                print(f"[4/5] 📄 Rendering {output_format.upper()}...")
            heartbeat.current_step = "render"

            with MemoryGuard("rendering") as mg:
                ast_path = out_dir / "ast_transformed.json"
                ast_json = ast_path.read_text() if ast_path.exists() else doc.pandoc_json

                ext = "tex" if output_format == "latex" else output_format
                output_path = out_dir / f"paper.{ext}"

                export_result = export_document(
                    ast_json, str(output_path), output_format,
                    journal=journal,
                    bibliography=bibliography,
                )
                mg.checkpoint("render_complete")

                ledger.save_checkpoint(run_id, "render", {
                    "success": export_result.success,
                    "output_path": export_result.output_path,
                    "size_bytes": export_result.size_bytes,
                })
                ledger.log_step(run_id, file_id, "render", "completed",
                               metadata={"success": export_result.success})

            if export_result.success:
                result["outputs"][output_format] = {
                    "path": export_result.output_path,
                    "size_bytes": export_result.size_bytes,
                }
                heartbeat.update(bytes_written=export_result.size_bytes)

                if not quiet:
                    size_kb = export_result.size_bytes / 1024
                    print(f"  ✅ Rendered: {output_path} ({size_kb:.1f} KB)")
            else:
                result["warnings"].append(f"Render failed: {export_result.error}")
                if not quiet:
                    print(f"  ⚠️  Render failed: {export_result.error}")

            # Also render LaTeX source for PDF output
            if output_format == "pdf":
                latex_path = out_dir / "paper.tex"
                if not latex_path.exists():
                    latex_result = export_document(
                        ast_json, str(latex_path), "latex", journal=journal,
                        bibliography=bibliography,
                    )
                    if latex_result.success:
                        result["outputs"]["latex"] = {
                            "path": latex_result.output_path,
                            "size_bytes": latex_result.size_bytes,
                        }

            heartbeat.complete_step("render")
        else:
            if not quiet:
                print("[4/5] ⏭️  Rendering already completed (resuming)")

        result["steps"]["render"] = "completed"

        # ═══════════════════════════════════════════════════════════════
        # PHASE 5: FINALIZE
        # ═══════════════════════════════════════════════════════════════
        if "finalize" not in completed_steps:
            if not quiet:
                print("[5/5] 📦 Finalizing...")
            heartbeat.current_step = "finalize"

            with MemoryGuard("finalize") as mg:
                # Write manifest
                manifest = {
                    "run_id": run_id,
                    "journal": journal,
                    "input_file": input_file,
                    "input_format": doc.source_format,
                    "output_format": output_format,
                    "outputs": result["outputs"],
                    "audit_score": result.get("audit", {}).get("score", 0),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "title": doc.title,
                    "authors": doc.authors,
                }
                manifest_path = out_dir / "manifest.json"
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f, indent=2)

                mg.checkpoint("finalize_complete")

                ledger.save_checkpoint(run_id, "finalize", manifest)
                ledger.log_step(run_id, file_id, "finalize", "completed")

            heartbeat.complete_step("finalize")
        else:
            if not quiet:
                print("[5/5] ⏭️  Finalize already completed (resuming)")

        result["steps"]["finalize"] = "completed"
        result["success"] = True

        # Complete the run
        ledger.complete_run(run_id, json.dumps(result, default=str))

        if not quiet:
            print(f"\n{'='*60}")
            print(f"  ✅ Pipeline complete!")
            print(f"  Output: {out_dir}")
            print(f"  Memory: {get_rss_mb():.0f} MB")
            print(f"{'='*60}\n")

    except KeyboardInterrupt:
        heartbeat.add_blocker("Pipeline interrupted by user")
        result["errors"].append("Interrupted by user")
        ledger.fail_run(run_id, "Interrupted")

    except Exception as e:
        heartbeat.add_blocker(f"Pipeline error: {str(e)}")
        result["errors"].append(str(e))
        ledger.fail_run(run_id, str(e))
        if not quiet:
            print(f"\n❌ Pipeline failed: {e}")

    finally:
        heartbeat.stop()
        force_gc()
        ledger.close()

    return result


def _build_ast_from_doc(doc: UnifiedDocument) -> str:
    """Build a minimal Pandoc JSON AST from a parsed document."""
    blocks = []

    # Title
    if doc.title:
        blocks.append({
            "t": "Header",
            "c": [1, ["title", [], []], [{"t": "Str", "c": doc.title}]]
        })

    # Abstract
    if doc.abstract:
        blocks.append({
            "t": "Div",
            "c": [["abstract", [], []], [
                {"t": "Header", "c": [2, ["abstract-title"], [{"t": "Str", "c": "Abstract"}]]},
                {"t": "Para", "c": [{"t": "Str", "c": doc.abstract}]}
            ]]
        })

    # Sections
    for section in doc.sections:
        level = section.get("level", 1)
        title = section.get("title", "")
        content = section.get("content", "")

        if title:
            blocks.append({
                "t": "Header",
                "c": [level, ["section"], [{"t": "Str", "c": title}]]
            })
        if content:
            blocks.append({
                "t": "Para",
                "c": [{"t": "Str", "c": content}]
            })

    # Equations
    for eq in doc.equations:
        blocks.append({
            "t": "Math",
            "c": ["DisplayMath", eq]
        })

    # Metadata
    meta = {}
    if doc.title:
        meta["title"] = {"t": "MetaInlines", "c": [{"t": "Str", "c": doc.title}]}
    if doc.authors:
        meta["author"] = {
            "t": "MetaList",
            "c": [{"t": "MetaInlines", "c": [{"t": "Str", "c": a}]} for a in doc.authors]
        }
    if doc.abstract:
        meta["abstract"] = {"t": "MetaInlines", "c": [{"t": "Str", "c": doc.abstract}]}

    ast = {
        "pandoc-api-version": [1, 23, 1],
        "meta": meta,
        "blocks": blocks
    }

    return json.dumps(ast)


# ── CLI Entry Point ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="translator",
        description="PaperForge — Universal Agentic Research-to-Journal Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 pipeline/translator.py paper.md --journal ieee --format docx
  python3 pipeline/translator.py thesis.tex --journal springer
  python3 pipeline/translator.py draft.docx --journal acm --format pdf
  python3 pipeline/translator.py --resume 20260418-123456-abcd1234
  python3 pipeline/translator.py --list-journals
        """
    )

    parser.add_argument("input", nargs="?", help="Input document file (.docx, .md, .tex, .jats)")
    parser.add_argument("--journal", "-j", default="ieee",
                       help="Target journal (default: ieee)")
    parser.add_argument("--format", "-f", default="docx",
                       choices=["pdf", "docx", "latex", "tex", "jats", "html", "epub"],
                       help="Output format (default: docx)")
    parser.add_argument("--output", "-o", help="Output directory")
    parser.add_argument("--resume", help="Resume a previous run by run ID")
    parser.add_argument("--max-minutes", type=int, default=45,
                       help="Session wall-time limit (default: 45)")
    parser.add_argument("--skip-visual-audit", action="store_true",
                       help="Skip visual SSIM audit")
    parser.add_argument("--bibliography", "-b", help="Path to .bib bibliography file")
    parser.add_argument("--list-journals", action="store_true",
                       help="List all available journal templates")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Suppress progress output")

    args = parser.parse_args()

    if args.list_journals:
        from src.templates.manager import TEMPLATE_URLS
        print("\nAvailable journal templates:\n")
        for key in sorted(TEMPLATE_URLS.keys()):
            info = TEMPLATE_URLS[key]
            print(f"  {key:<25} {info['name']}")
        print(f"\nTotal: {len(TEMPLATE_URLS)} journal templates")
        return

    if not args.input and not args.resume:
        parser.print_help()
        return

    if not args.input and args.resume:
        # Load from checkpoint
        ledger = Ledger()
        checkpoint = ledger.get_latest_checkpoint(args.resume)
        if checkpoint:
            state = checkpoint["state"]
            args.input = state.get("input_file", "")
        ledger.close()

    result = run_pipeline(
        input_file=args.input,
        journal=args.journal,
        output_format=args.format,
        output_dir=args.output,
        resume_run_id=args.resume,
        max_minutes=args.max_minutes,
        skip_visual_audit=args.skip_visual_audit,
        bibliography=args.bibliography,
        quiet=args.quiet,
    )

    # Exit code based on success
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
