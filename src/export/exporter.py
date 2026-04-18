"""
PaperForge — Export Module
Renders documents in multiple formats: PDF, DOCX, LaTeX, JATS XML, HTML, ePub.
"""
import json
import subprocess
import pathlib
import tempfile
import shutil
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


SUPPORTED_OUTPUT_FORMATS = ["pdf", "docx", "latex", "tex", "jats", "html", "epub", "rtf", "odt"]


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool = False
    output_path: str = ""
    format: str = ""
    size_bytes: int = 0
    warnings: List[str] = field(default_factory=list)
    error: str = ""


def export_document(ast_json: str, output_path: str, fmt: str,
                    journal: str = "ieee",
                    templates_dir: Optional[pathlib.Path] = None,
                    csl_file: Optional[str] = None,
                    bibliography: Optional[str] = None,
                    extra_args: Optional[List[str]] = None) -> ExportResult:
    """
    Export a Pandoc AST to the specified format.
    """
    result = ExportResult(format=fmt)
    out_path = pathlib.Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build Pandoc command
    cmd = ["pandoc", "-f", "json", "-o", str(out_path)]

    # Add output format hints
    if fmt in ("latex", "tex"):
        cmd.extend(["--standalone", "--wrap=none"])
    elif fmt == "pdf":
        cmd.extend(["--pdf-engine=xelatex"])
    elif fmt == "docx":
        pass  # Pandoc handles this natively
    elif fmt == "jats":
        cmd.extend(["--standalone"])
    elif fmt == "html":
        cmd.extend(["--standalone", "--self-contained"])
    elif fmt == "epub":
        cmd.extend(["--standalone"])

    # Add CSL for citation formatting
    if csl_file:
        csl_path = pathlib.Path(csl_file)
        if csl_path.exists():
            cmd.append(f"--csl={csl_path}")
    else:
        # Try default CSL
        csl_dir = pathlib.Path(__file__).parent.parent.parent / "data" / "csl-styles"
        if csl_dir.exists():
            csl_default = csl_dir / "ieee.csl"
            if csl_default.exists():
                cmd.append(f"--csl={csl_default}")

    # Add bibliography
    if bibliography and pathlib.Path(bibliography).exists():
        cmd.append(f"--bibliography={bibliography}")

    # Add template
    if templates_dir:
        template_path = templates_dir / journal / f"template.{fmt}"
        if template_path.exists():
            cmd.append(f"--template={template_path}")

    # Add journal metadata
    cmd.extend([
        "-V", f"journal={journal}",
    ])

    # Add extra args
    if extra_args:
        cmd.extend(extra_args)

    try:
        # Use MemoryGuard if available, otherwise run directly
        result_proc = subprocess.run(
            cmd,
            input=ast_json,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result_proc.returncode == 0 and out_path.exists():
            result.success = True
            result.output_path = str(out_path.resolve())
            result.size_bytes = out_path.stat().st_size
        else:
            result.error = result_proc.stderr[:500] if result_proc.stderr else "Unknown error"
            result.warnings.append(f"Pandoc returned code {result_proc.returncode}")

            # Try without PDF engine
            if fmt == "pdf" and "xelatex" not in result_proc.stderr:
                cmd2 = ["pandoc", "-f", "json", "-o", str(out_path)]
                result_proc2 = subprocess.run(
                    cmd2, input=ast_json, capture_output=True, text=True, timeout=120
                )
                if result_proc2.returncode == 0 and out_path.exists():
                    result.success = True
                    result.output_path = str(out_path.resolve())
                    result.size_bytes = out_path.stat().st_size
                    result.error = ""
                    result.warnings.append("Used fallback PDF engine")

    except subprocess.TimeoutExpired:
        result.error = "Export timed out (120s)"
    except FileNotFoundError:
        result.error = "Pandoc not found. Install pandoc for document export."
    except Exception as e:
        result.error = str(e)

    return result


def export_all_formats(ast_json: str, output_dir: str, journal: str = "ieee",
                       formats: Optional[List[str]] = None,
                       templates_dir: Optional[pathlib.Path] = None) -> Dict[str, ExportResult]:
    """
    Export document to multiple formats simultaneously.
    """
    if formats is None:
        formats = ["docx", "latex", "html"]

    out_dir = pathlib.Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for fmt in formats:
        if fmt not in SUPPORTED_OUTPUT_FORMATS:
            results[fmt] = ExportResult(
                success=False, format=fmt,
                error=f"Unsupported format: {fmt}"
            )
            continue

        ext = "tex" if fmt == "latex" else fmt
        out_path = out_dir / f"output.{ext}"

        results[fmt] = export_document(
            ast_json, str(out_path), fmt, journal, templates_dir
        )

    return results


def export_jats(ast_json: str, output_path: str) -> ExportResult:
    """
    Export to JATS XML format specifically.
    """
    return export_document(ast_json, output_path, "jats")


def export_docx_with_template(ast_json: str, output_path: str,
                              reference_docx: str) -> ExportResult:
    """
    Export DOCX using a reference document for styling.
    """
    result = ExportResult(format="docx")
    out_path = pathlib.Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "pandoc", "-f", "json", "-o", str(out_path),
        f"--reference-doc={reference_docx}"
    ]

    try:
        proc = subprocess.run(
            cmd, input=ast_json, capture_output=True, text=True, timeout=120
        )
        if proc.returncode == 0 and out_path.exists():
            result.success = True
            result.output_path = str(out_path.resolve())
            result.size_bytes = out_path.stat().st_size
        else:
            result.error = proc.stderr[:500]
    except Exception as e:
        result.error = str(e)

    return result


def export_pdf_via_tectonic(latex_path: str, output_path: str) -> ExportResult:
    """
    Export PDF using Tectonic (if available) for high-quality rendering.
    Falls back to Pandoc if Tectonic is unavailable.
    """
    result = ExportResult(format="pdf")

    # Try Tectonic first
    try:
        proc = subprocess.run(
            ["tectonic", latex_path],
            capture_output=True, text=True, timeout=300,
            cwd=str(pathlib.Path(latex_path).parent)
        )
        pdf_path = pathlib.Path(latex_path).with_suffix('.pdf')
        if proc.returncode == 0 and pdf_path.exists():
            dest = pathlib.Path(output_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(pdf_path), str(dest))
            result.success = True
            result.output_path = str(dest.resolve())
            result.size_bytes = dest.stat().st_size
            return result
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: Pandoc
    try:
        proc = subprocess.run(
            ["pandoc", latex_path, "-o", output_path, "--pdf-engine=xelatex"],
            capture_output=True, text=True, timeout=300
        )
        if proc.returncode == 0 and pathlib.Path(output_path).exists():
            result.success = True
            result.output_path = str(pathlib.Path(output_path).resolve())
            result.size_bytes = pathlib.Path(output_path).stat().st_size
        else:
            result.error = proc.stderr[:500]
    except FileNotFoundError:
        result.error = "Neither Tectonic nor Pandoc available for PDF export"
    except Exception as e:
        result.error = str(e)

    return result
